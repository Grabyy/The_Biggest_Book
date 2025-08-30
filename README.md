# 📚 The Biggest Book

A **Streamlit + SQLAlchemy** web app to manage and explore books.  
Users can add books (from Open Library or manually), tag them with authors & subjects, and leave reviews.  
The app computes **book volumes** from dimensions, lets you browse and filter, and even generates fun analytics (like biggest books by volume).

---

## 🚀 Features

- 🔍 **Search & Add Books**
  - Fetch metadata from [Open Library](https://openlibrary.org/) by **title** or **ISBN**
  - Manually add books if not available in Open Library
- 📑 **Book Catalog**
  - Browse all books with cover, title, authors, and subjects
  - Titles link to **Open Library** (if available) or fallback to **Google search**
- 📝 **Reviews**
  - Each user can review a book (⭐ rating + optional text)
  - Average ratings and recent reviews are shown
- 📏 **Dimensions & Volume**
  - Store height, width, thickness, pages
  - Auto-compute book volume (cm³) — compare which book is the *biggest*
- 📊 **Analytics**
  - Aggregated graphs (page counts, volumes, subjects, ratings)
- 🗄️ **SQL-powered backend**
  - Models defined with SQLAlchemy ORM
  - Relational schema with users, books, authors, subjects, and reviews

---

## 🛠️ Tech Stack

- [Streamlit](https://streamlit.io/) — UI
- [SQLAlchemy](https://www.sqlalchemy.org/) — ORM and DB models
- SQLite (default) — database backend
- Open Library API — for book metadata

---

## 📂 Project Structure

```bash
The_Biggest_Book/
│
├── app.py # main Streamlit entrypoint
├── models.py # SQLAlchemy ORM models
├── dal.py # Data access layer (CRUD functions)
├── db.py # Session/engine setup
├── tabs/
│ ├── add.py # Add books (Open Library & manual)
│ ├── browse.py # Browse catalog + inline reviews
│ ├── analytics.py # Charts and comparisons
│ └── ... # (other tabs)
├── harvesters/
│ └── openlibrary_client.py # API client for Open Library
└── README.md # this file
```


---

## 🏃 Getting Started


```bash
git clone https://github.com/YOURNAME/The_Biggest_Book.git
cd The_Biggest_Book

conda create -n book streamlit sqlalchemy pandas python
conda activate book
streamlit run app.py
```


