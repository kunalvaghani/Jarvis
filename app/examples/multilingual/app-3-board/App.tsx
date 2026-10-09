import React, { useState, useEffect, useRef } from "react";

type Priority = "low" | "medium" | "high";
type Status = "todo" | "doing" | "done";

interface Task {
  id: string;
  title: string;
  priority: Priority;
  status: Status;
}

const STORAGE_KEY = "kanban-tasks";

function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [search, setSearch] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setTasks(JSON.parse(saved));
    } catch {
      setError("Failed to load tasks");
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    } catch {
      setError("Failed to save tasks");
    }
  }, [tasks]);

  useEffect(()=>{if(showDialog)titleRef.current?.focus()},[showDialog]);

  const filtered = tasks.filter(
    (t) => t.title.toLowerCase().includes(search.toLowerCase())
  );

  const openNew = () => {
    setTitle("");
    setPriority("medium");
    setEditingTask(null);
    setShowDialog(true);
    titleRef.current?.focus();
  };

  const openEdit = (task: Task) => {
    setTitle(task.title);
    setPriority(task.priority);
    setEditingTask(task);
    setShowDialog(true);
    titleRef.current?.focus();
  };

  const saveTask = () => {
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    if (editingTask) {
      setTasks((prev) =>
        prev.map((t) =>
          t.id === editingTask.id
            ? { ...t, title, priority } as Task
            : t
        )
      );
    } else {
      setTasks((prev) => [
        ...prev,
        { id: crypto.randomUUID(), title, priority, status: "todo" },
      ]);
    }
    setError("");
    setShowDialog(false);
    setTitle("");
    setPriority("medium");
  };

  const deleteTask = (id: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== id));
  };

  const moveTask = (id: string, newStatus: Status) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, status: newStatus } : t))
    );
  };

  const handleDragStart = (e: React.DragEvent, id: string) => {
    setDraggedId(id);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain",id);
  };

  const handleDrop = (e: React.DragEvent, status: Status) => {
    e.preventDefault();
    const id=e.dataTransfer.getData("text/plain")||draggedId;
    if(id)moveTask(id,status);
    setDraggedId(null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const doneCount = tasks.filter((t) => t.status === "done").length;

  return (
    <div style={styles.container}>
      <style>{`*{box-sizing:border-box}body{margin:0}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #008bd3;outline-offset:3px}@keyframes ambient{50%{background-color:#e2eefa}}@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}`}</style>
      <h1 style={styles.title}>Studio Board</h1>
      {error && <div style={styles.error}>{error}</div>}
      <input
        id="search"
        type="text"
        placeholder="Search tasks..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={styles.search}
      />
      <button id="add" onClick={openNew} style={styles.button}>
        Add task
      </button>
      <div style={styles.summary} id="summary">
        Done: {doneCount}
      </div>
      {search && filtered.length===0 && <p role="status">No results</p>}
      <div style={styles.board}>
        {(["todo", "doing", "done"] as Status[]).map((status) => (
          <div
            key={status}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, status)}
            style={{
              ...styles.column,
              background:
                status === "todo"
                  ? "#e3f2fd"
                  : status === "doing"
                  ? "#fff3e0"
                  : "#e8f5e9",
            }}
          >
            <h2 style={styles.columnTitle}>
              {status.toUpperCase()} ({filtered.filter((t) => t.status === status).length})
            </h2>
            {filtered
              .filter((t) => t.status === status)
              .map((task) => (
                <div
                  key={task.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, task.id)}
                  style={{
                    ...styles.card,
                    background:
                      task.priority === "high"
                        ? "#ffebee"
                        : task.priority === "medium"
                        ? "#fff8e1"
                        : "#f3e5f5",
                  }}
                >
                  <div style={styles.cardTitle}>{task.title}</div><small>{task.priority} priority</small>
                  <div style={styles.cardActions}>
                    {status !== "todo" && (
                      <button
                        onClick={() => moveTask(task.id, status === "doing" ? "done" : "todo")}
                        style={styles.smallButton}
                      >
                        Move to {status === "doing" ? "Done" : "Todo"}
                      </button>
                    )}
                    {status !== "done" && (
                      <button
                        onClick={() => moveTask(task.id, status === "todo" ? "doing" : "todo")}
                        style={styles.smallButton}
                      >
                        Move to {status === "todo" ? "Doing" : "Todo"}
                      </button>
                    )}
                    <button onClick={() => openEdit(task)} style={styles.smallButton}>
                      Edit
                    </button>
                    <button onClick={() => deleteTask(task.id)} style={styles.deleteButton}>
                      Delete
                    </button>
                  </div>
                </div>
              ))}
          </div>
        ))}
      </div>
      {showDialog && (
        <div style={styles.overlay}>
          <div style={styles.dialog} role="dialog" aria-modal="true" aria-label="Task editor" onKeyDown={e=>{if(e.key==="Escape")setShowDialog(false);if(e.key==="Tab"){const controls=e.currentTarget.querySelectorAll<HTMLElement>("input,select,button");const first=controls[0],last=controls[controls.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}}}>
            <h3>{editingTask ? "Edit Task" : "New Task"}</h3>
            <input
              ref={titleRef}
              id="taskTitle" aria-label="Task title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={styles.input}
            />
            <select aria-label="Task priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority)}
              style={styles.select}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
            <div style={styles.dialogButtons}>
              <button onClick={saveTask} style={styles.button}>
                Save
              </button>
              <button onClick={() => setShowDialog(false)} style={styles.button}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    fontFamily: "system-ui, -apple-system, sans-serif",
    padding: "1rem",
    minHeight: "100vh",
    animation: "ambient 8s ease-in-out infinite",
    background: "#f5f5f5",
    color: "#333",
  },
  title: {
    textAlign: "center",
    marginBottom: "1rem",
    fontSize: "1.75rem",
  },
  search: {
    width: "100%",
    maxWidth: "400px",
    padding: "0.5rem",
    marginBottom: "0.5rem",
    borderRadius: "4px",
    border: "1px solid #ccc",
  },
  button: {
    padding: "0.5rem 1rem",
    backgroundColor: "#1976d2",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "1rem",
  },
  summary: {
    textAlign: "center",
    marginBottom: "1rem",
    color: "#666",
  },
  board: {
    display: "flex",
    gap: "1rem",
    flexWrap: "wrap",
    justifyContent: "center",
  },
  column: {
    flex: "1 1 250px",
    minWidth: "200px",
    padding: "0.75rem",
    borderRadius: "8px",
    minHeight: "400px",
  },
  columnTitle: {
    margin: "0 0 0.5rem",
    fontSize: "1.1rem",
  },
  card: {
    padding: "0.75rem",
    marginBottom: "0.5rem",
    borderRadius: "6px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
    cursor: "grab",
  },
  cardTitle: {
    margin: "0 0 0.5rem",
    fontWeight: "500",
  },
  cardActions: {
    display: "flex",
    gap: "0.25rem",
    flexWrap: "wrap",
  },
  smallButton: {
    padding: "0.25rem 0.5rem",
    fontSize: "0.75rem",
    border: "none",
    borderRadius: "3px",
    cursor: "pointer",
    backgroundColor: "#e0e0e0",
  },
  deleteButton: {
    padding: "0.25rem 0.5rem",
    fontSize: "0.75rem",
    border: "none",
    borderRadius: "3px",
    cursor: "pointer",
    backgroundColor: "#ef5350",
    color: "white",
  },
  overlay: {
    position: "fixed" as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: "rgba(0,0,0,0.5)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  dialog: {
    background: "white",
    padding: "1rem",
    borderRadius: "8px",
    width: "90%",
    maxWidth: "400px",
    boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
  },
  input: {
    width: "100%",
    padding: "0.5rem",
    marginBottom: "0.5rem",
    border: "1px solid #ccc",
    borderRadius: "4px",
    boxSizing: "border-box" as const,
  },
  select: {
    width: "100%",
    padding: "0.5rem",
    marginBottom: "0.5rem",
    border: "1px solid #ccc",
    borderRadius: "4px",
    boxSizing: "border-box" as const,
  },
  dialogButtons: {
    display: "flex",
    gap: "0.5rem",
    justifyContent: "flex-end",
  },
  error: {
    background: "#ffebee",
    color: "#c62828",
    padding: "0.5rem",
    borderRadius: "4px",
    textAlign: "center",
    marginBottom: "1rem",
  },
};

export default App;
