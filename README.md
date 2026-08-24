Here is the complete `README.md` content:

````markdown
# FinMan

FinMan is an AI-powered personal finance assistant that helps users analyze their bank statements and understand their spending.

## Features

- Upload bank statements in CSV or Excel format
- Automatically categorize transactions
- View income, expenses, and cash flow
- Analyze spending by category
- Track recurring subscriptions
- Search and filter transactions
- Ask natural-language questions about finances
- Generate AI-powered financial insights

## Tech Stack

### Frontend

- React
- Vite
- CSS

### Backend

- Python
- FastAPI
- LangChain
- LangGraph
- Google Gemini

### Data Processing

- Pandas
- NumPy
- OpenPyXL

## Getting Started

### Backend

Navigate to the backend directory:

```bash
cd backend
````

Create a virtual environment:

```bash
python -m venv venv
```

Activate the virtual environment on Windows:

```bash
venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the backend directory:

```env
GEMINI_API_KEY=your_api_key
```

Start the backend server:

```bash
uvicorn app.main:app --reload
```

### Frontend

Navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

## Project Status

🚧 FinMan is currently under development.

More features, improvements, and documentation will be added as the project progresses.

````
