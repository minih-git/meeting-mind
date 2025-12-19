import { useState, useEffect } from "react";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import "./App.css";
import RecorderPage from "./components/RecorderPage";
import HistoryPage from "./components/HistoryPage";

function App() {
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route
          path="/home"
          element={<RecorderPage theme={theme} toggleTheme={toggleTheme} />}
        />
        <Route path="/history" element={<HistoryPage theme={theme} />} />
        <Route path="/history/detail" element={<HistoryPage theme={theme} />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
