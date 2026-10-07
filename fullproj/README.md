# Smart Attendance Manager

A beginner-friendly Flask + SQLite attendance management project.

## Features

- Student login and dashboard
- Admin/faculty dashboard
- Add and delete subjects
- Modify number of classes
- Conduct classes one at a time
- Mark demo student's Present/Absent attendance
- Duplicate attendance prevention
- Attendance percentage and status
- Attendance prediction information
- AJAX admin actions without page reload or scroll jumping

## Demo login

Student:
- Email: `student@college.com`
- Password: `student123`

Admin:
- Email: `admin@college.com`
- Password: `admin123`

## Run on Windows

Open PowerShell inside the project folder:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Then open:

`http://127.0.0.1:5000`

## Important

The application creates `attendance.db` automatically when it starts. If you already have an attendance database, keep your existing `attendance.db` instead of replacing it.
