from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client
import os
import tempfile
# from weasyprint import HTML
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Assign current timestamp to a variable
timestamp1 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
SUPABASE_URL = "https://nizvcdssajfpjtncbojx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5penZjZHNzYWpmcGp0bmNib2p4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI2MTU0ODksImV4cCI6MjA1ODE5MTQ4OX0.5b2Yzfzzzz-C8S6iqhG3SinKszlgjdd4NUxogWIxCLc"
BUCKET_NAME = "student-reports"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],
)

class StoreGeneralRequest(BaseModel):
    student_id: int
    program_id: int
    educator_employee_id: int
    quarter: str
    punctuality: str = None
    preparedness: str = None
    any_behavioral_issues: str = None
    assistance_required: str = None
    parental_support: str = None

class GenerateReportRequest(BaseModel):
    student_id: int
    program_id: int
    educator_employee_id: int
    quarter: str

@app.get("/")
def home():
    return {"message": "Hello, this is the FastAPI home page!"}



@app.post("/store_general_reporting")
def store_general_reporting(data: StoreGeneralRequest):
    try:
        report_data = (
            supabase.table("general_reporting")
            .select("*")
            .eq("student_id", data.student_id)
            .eq("program_id", data.program_id)
            .eq("educator_employee_id", data.educator_employee_id)
            .eq("quarter", data.quarter)
            .execute()
        ).data
        update_data = {k: v for k, v in data.dict().items() if v is not None and k not in ["student_id", "program_id", "educator_employee_id", "quarter"]}

        if report_data:
            existing_record = report_data[0]
            for col in update_data:
                if existing_record.get(col):
                    update_data[col] = existing_record[col] + ' ' + update_data[col]
            supabase.table("general_reporting").update(update_data).eq("student_id", data.student_id).eq("program_id", data.program_id).eq("educator_employee_id", data.educator_employee_id).eq("quarter", data.quarter).execute()
        else:
            update_data.update({
                "student_id": data.student_id,
                "program_id": data.program_id,
                "educator_employee_id": data.educator_employee_id,
                "quarter": data.quarter
            })
            supabase.table("general_reporting").insert(update_data).execute()
        
        return {"message": "General reporting stored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Image
import tempfile
import os
from fastapi.responses import FileResponse

@app.post("/generate_report")
def generate_report(data: GenerateReportRequest):
    try:
        student_id, program_id, educator_employee_id, quarter = data.student_id, data.program_id, data.educator_employee_id, data.quarter

        print("Fetching data from Supabase...")
        general_data = supabase.table("general_reporting").select("*").eq("student_id", student_id).eq("program_id", program_id).eq("educator_employee_id", educator_employee_id).eq("quarter", quarter).execute().data
        performance_data = supabase.table("performance_records").select("*").eq("student_id", student_id).eq("program_id", program_id).eq("educator_employee_id", educator_employee_id).eq("quarter", quarter).execute().data

        if not general_data or not performance_data:
            print("No data found")
            raise HTTPException(status_code=404, detail="No data found")

        general_data = general_data[0]
        performance_data = performance_data[0]

        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        c = canvas.Canvas(temp_pdf.name, pagesize=letter)
        width, height = letter
        styles = getSampleStyleSheet()
        styleN = styles["Normal"]

        def add_page_number(canvas, doc):
            """Adds the page number to the bottom of each page."""
            page_num = canvas.getPageNumber()
            text = "Page %s" % page_num
            canvas.saveState()
            canvas.setFont('Times-Roman', 9)
            canvas.drawString(inch, 0.75 * inch, text)
            canvas.restoreState()

        def draw_watermark(canvas, logo_path):
            """Draws a semi-transparent watermark."""
            canvas.saveState()
            canvas.setFillGray(0.9, 0.2)  # Gray color with 0.2 opacity
            canvas.setFont('Helvetica', 60)
            # canvas.drawCentredString(width / 2.0, height / 2.0, 'WATERMARK') # simple text watermark. remove it if you have image.
            try:
                img = ImageReader(logo_path)
                canvas.drawImage(img, width / 4, height / 4, width=width / 2, height=height / 2, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"Error loading or drawing logo: {e}")
            canvas.restoreState()
        
        y_position = 750
        page_number = 1

        def new_page():
            nonlocal y_position, page_number
            c.showPage()
            add_page_number(c, c)
            draw_watermark(c, logo_path)
            y_position = 750  # Reset y_position for the new page
            page_number += 1

        logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.jpg')  # Correct logo path
        draw_watermark(c, logo_path) # Adding water mark on first page.
        add_page_number(c, c) # Adding page number on first page.


        # Title
        c.setFillColor(colors.blue)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, y_position, "Ishanya India Foundation Student Report")
        y_position -= 30
        if y_position < 50:
            new_page()

        # Student Info Table
        student_details = [["Student ID", student_id], ["Program ID", program_id], ["Employee ID", educator_employee_id], ["Quarter", quarter]]
        student_table = Table(student_details, colWidths=[2 * inch, 4 * inch])
        student_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.royalblue),  #Blue color theme
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        student_table.wrapOn(c, 100, y_position)
        student_table.drawOn(c, 100, y_position - 60)
        y_position -= 100
        if y_position < 50:
            new_page()

        # General Reporting
        general_fields = {
            "Punctuality": general_data.get("punctuality"),
            "Preparedness": general_data.get("preparedness"),
            "Behavioral Issues": general_data.get("any_behavioral_issues"),
            "Assistance Required": general_data.get("assistance_required"),
            "Parental Support": general_data.get("parental_support")
        }
        general_fields = {k: v for k, v in general_fields.items() if v}

        if general_fields:
            c.setFillColor(colors.forestgreen)  # Green color theme
            c.setFont("Helvetica-Bold", 14)
            # Using Paragraph for dynamic positioning
            p = Paragraph("<b>General Reporting</b>", styles['h2']) # Using Paragraph to write.
            p.wrapOn(c, width - 200, height)
            p.drawOn(c, 100, y_position)
            y_position -= 30
            if y_position < 50:
                new_page()

            general_table = Table([[key, value] for key, value in general_fields.items()], colWidths=[2.5 * inch, 3.5 * inch])
            general_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.seagreen), #Green color theme
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            general_table.wrapOn(c, 100, y_position)
            general_table.drawOn(c, 100, y_position - 40)
            y_position -= (len(general_fields) * 30 + 20)  # Adjust spacing dynamically
            if y_position < 50:
                new_page()

        # Performance Records Table
        c.setFillColor(colors.darkblue)
        c.setFont("Helvetica-Bold", 14)
        p = Paragraph("<b>Performance Records</b>", styles['h2'])  # Using Paragraph to write.
        p.wrapOn(c, width - 200, height)
        p.drawOn(c, 100, y_position)
        y_position -= 30
        if y_position < 50:
            new_page()

        performance_table_data = [["Week", "Description", "Score"]]
        for i in range(1, 17):
            desc = performance_data.get(f"{i}_description", "")
            score = performance_data.get(f"{i}_score", "")
            if desc or score:
                performance_table_data.append([f"Week {i}", desc, score])

        if len(performance_table_data) > 1:
            performance_table = Table(performance_table_data, colWidths=[1.2 * inch, 3.5 * inch, 1.2 * inch])
            performance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.dodgerblue),  # Blue color theme
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            performance_table.wrapOn(c, 100, y_position)
            performance_table.drawOn(c, 100, y_position - (len(performance_table_data) * 20))
            y_position -= (len(performance_table_data) * 20 + 20) # Adjust spacing dynamically

        if y_position < 50:
            new_page()

        c.save()
        print("PDF generated successfully!")

        file_path = f"{student_id}/{program_id}/{quarter}/{timestamp1}_report.pdf"
        with open(temp_pdf.name, "rb") as file:
            supabase.storage.from_(BUCKET_NAME).upload(file_path, file, {"content-type": "application/pdf"})
            print("Uploaded to the bucket")

        file_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"
        supabase.table("reports").insert({
            "student_id": student_id,
            "program_id": program_id,
            "educator_employee_id": educator_employee_id,
            "quarter": quarter,
            "url": file_url
        }).execute()
        print("Database updated with the report URL")

        response = FileResponse(temp_pdf.name, filename=f"{student_id}_{program_id}_{quarter}_{timestamp1}_report.pdf", media_type="application/pdf")
        return response
    except Exception as e:
        print("Error generating report:", str(e))
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
