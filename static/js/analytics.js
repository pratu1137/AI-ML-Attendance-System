(() => {
    const data = window.analyticsData || { daily: [], subjects: [] };
    if (typeof Chart === "undefined") return;
    const dailyCanvas = document.getElementById("daily-attendance-chart");
    const subjectCanvas = document.getElementById("subject-attendance-chart");
    if (dailyCanvas) {
        new Chart(dailyCanvas, {
            type: "line",
            data: { labels: data.daily.map((row) => row.date), datasets: [{ label: "Attendance %", data: data.daily.map((row) => row.percentage), borderColor: "#198754", tension: 0.2 }] },
            options: { scales: { y: { beginAtZero: true, max: 100 } } },
        });
    }
    if (subjectCanvas) {
        new Chart(subjectCanvas, {
            type: "bar",
            data: { labels: data.subjects.map((row) => row.subject_code), datasets: [{ label: "Attendance %", data: data.subjects.map((row) => row.percentage), backgroundColor: "#0d6efd" }] },
            options: { scales: { y: { beginAtZero: true, max: 100 } } },
        });
    }
})();