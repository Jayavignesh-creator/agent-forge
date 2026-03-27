from io import BytesIO

import requests
from pypdf import PdfReader


def extract_pdf_text_from_url(url: str, timeout: int = 30) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not url.lower().endswith(".pdf"):
        raise ValueError(f"URL does not appear to be a PDF: {content_type}")

    reader = PdfReader(BytesIO(response.content))
    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    return "\n".join(pages).strip()


if __name__ == "__main__":
    pdf_url = "https://cs.au.dk/~amoeller/papers/tajs/paper.pdf"
    text = extract_pdf_text_from_url(pdf_url)
    print(text[:5000])
