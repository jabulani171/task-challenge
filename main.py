from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORS

app = FastAPI()

# Enable CORS for local testing
app.add_middleware(
    CORS,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for Task
class Task(BaseModel):
    title: str
    description: str
    status: str  # "Pending" or "Completed"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("tasks.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Helper function to connect to the database
def get_db():
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn

# Create a new task
@app.post("/tasks/", response_model=Task)
def create_task(task: Task):
    if task.status not in ["Pending", "Completed"]:
        raise HTTPException(status_code=400, detail="Status must be 'Pending' or 'Completed'")
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)",
        (task.title, task.description, task.status)
    )
    conn.commit()
    conn.close()
    return task

# Update an existing task
@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    existing_task = c.fetchone()
    if not existing_task:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = {}
    if task.title:
        update_data["title"] = task.title
    if task.description:
        update_data["description"] = task.description
    if task.status:
        if task.status not in ["Pending", "Completed"]:
            conn.close()
            raise HTTPException(status_code=400, detail="Status must be 'Pending' or 'Completed'")
        update_data["status"] = task.status
    
    if update_data:
        query = "UPDATE tasks SET " + ", ".join(f"{k} = ?" for k in update_data.keys()) + " WHERE id = ?"
        c.execute(query, list(update_data.values()) + [task_id])
        conn.commit()
    
    conn.close()
    return {"message": "Task updated successfully"}

# Delete a task
@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"message": "Task deleted successfully"}

# Retrieve all tasks with optional status filter
@app.get("/tasks/")
def get_tasks(status: Optional[str] = None):
    conn = get_db()
    c = conn.cursor()
    if status and status in ["Pending", "Completed"]:
        c.execute("SELECT * FROM tasks WHERE status = ?", (status,))
    else:
        c.execute("SELECT * FROM tasks")
    tasks = [dict(row) for row in c.fetchall()]
    conn.close()
    return tasks

# Calculate percentage of completed tasks per week
@app.get("/tasks/completion-percentage/")
def get_completion_percentage():
    conn = get_db()
    c = conn.cursor()
    
    # Get tasks from the last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    c.execute("SELECT status FROM tasks WHERE created_at >= ?", (week_ago,))
    tasks = c.fetchall()
    
    if not tasks:
        conn.close()
        return {"week": week_ago.strftime("%Y-%m-%d"), "completion_percentage": 0.0}
    
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if task["status"] == "Completed")
    percentage = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0.0
    
    conn.close()
    return {"week": week_ago.strftime("%Y-%m-%d"), "completion_percentage": round(percentage, 2)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
