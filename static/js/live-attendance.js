(() => {
    const video = document.getElementById("camera");
    const overlay = document.getElementById("face-overlay");
    const status = document.getElementById("camera-status");
    const facesDetected = document.getElementById("faces-detected");
    const result = document.getElementById("detection-result");
    const lectureStatus = document.getElementById("lecture-status");
    const studentStatus = document.getElementById("student-status");
    const startButton = document.getElementById("start-camera");
    const stopButton = document.getElementById("stop-camera");
    const csrfToken = document.getElementById("csrf-token").value;
    const captureCanvas = document.createElement("canvas");
    const frameIntervalMs = 1000;
    let stream = null;
    let timer = null;
    let requestInFlight = false;
    let completed = false;

    function setStatus(value) {
        status.textContent = value;
    }

    function clearOverlay() {
        overlay.width = video.videoWidth || 1;
        overlay.height = video.videoHeight || 1;
        overlay.getContext("2d").clearRect(0, 0, overlay.width, overlay.height);
    }

    function drawFaces(faces) {
        overlay.width = video.videoWidth;
        overlay.height = video.videoHeight;
        const scaleX = overlay.width / captureCanvas.width;
        const scaleY = overlay.height / captureCanvas.height;
        const context = overlay.getContext("2d");
        context.clearRect(0, 0, overlay.width, overlay.height);
        context.strokeStyle = "#20c997";
        context.lineWidth = Math.max(2, overlay.width / 320);
        faces.forEach((face) => context.strokeRect(face.x * scaleX, face.y * scaleY, face.width * scaleX, face.height * scaleY));
    }

    async function processFrame() {
        if (completed || requestInFlight || !stream || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
        requestInFlight = true;
        captureCanvas.width = Math.min(video.videoWidth, 960);
        captureCanvas.height = Math.round(captureCanvas.width * video.videoHeight / video.videoWidth);
        captureCanvas.getContext("2d").drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
        try {
            const blob = await new Promise((resolve) => captureCanvas.toBlob(resolve, "image/jpeg", 0.8));
            const formData = new FormData();
            formData.append("frame", blob, "camera-frame.jpg");
            const controller = new AbortController();
            const timeout = window.setTimeout(() => controller.abort(), 10000);
            const response = await fetch("/api/attendance/mark", {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: formData,
                signal: controller.signal,
            });
            window.clearTimeout(timeout);
            const payload = await response.json();
            if (!response.ok || !payload.success) throw new Error(payload.error || "Detection request failed.");
            drawFaces(payload.faces);
            facesDetected.textContent = String(payload.faces_detected || 0);
            if (payload.recorded) {
                result.textContent = `${payload.student.full_name} (${payload.student.roll_number}) - ${payload.message} (${payload.attendance.status})`;
                studentStatus.textContent = `${payload.student.full_name} (${payload.student.student_id})`;
                completed = true;
                if (timer) window.clearInterval(timer);
                timer = null;
            } else if (payload.reason === "NO_FACE") {
                result.textContent = "Searching for face...";
            } else if (payload.reason === "MULTIPLE_FACES") {
                result.textContent = "Multiple faces detected - please keep only one person in frame.";
            } else if (payload.reason === "ALREADY_RECORDED") {
                result.textContent = payload.student ? `${payload.student.full_name} (${payload.student.roll_number}) - ${payload.message}` : payload.message;
                if (payload.student) studentStatus.textContent = `${payload.student.full_name} (${payload.student.student_id})`;
            } else if (payload.reason === "NO_ACTIVE_LECTURE") {
                result.textContent = "NO ACTIVE LECTURE";
            } else {
                result.textContent = "Unknown student";
            }
        } catch (error) {
            result.textContent = error.message || "Network error while processing the frame.";
        } finally {
            requestInFlight = false;
        }
    }

    async function startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setStatus("ERROR: BROWSER UNSUPPORTED");
            return;
        }
        setStatus("REQUESTING PERMISSION");
        try {
            const lectureResponse = await fetch("/api/current-lecture");
            const lecture = await lectureResponse.json();
            lectureStatus.textContent = lecture.active ? `${lecture.subject_code} | ${lecture.faculty} | ${lecture.room}` : "NO ACTIVE LECTURE";
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
            video.srcObject = stream;
            await video.play();
            setStatus("ACTIVE");
            completed = false;
            startButton.disabled = true;
            stopButton.disabled = false;
            timer = window.setInterval(processFrame, frameIntervalMs);
        } catch (error) {
            setStatus(error.name === "NotAllowedError" ? "ERROR: PERMISSION DENIED" : "ERROR: CAMERA UNAVAILABLE");
            lectureStatus.textContent = "Unavailable";
            stream = null;
        }
    }

    function stopCamera() {
        if (timer) window.clearInterval(timer);
        timer = null;
        if (stream) stream.getTracks().forEach((track) => track.stop());
        stream = null;
        completed = false;
        video.srcObject = null;
        clearOverlay();
        facesDetected.textContent = "0";
        studentStatus.textContent = "-";
        setStatus("OFFLINE");
        startButton.disabled = false;
        stopButton.disabled = true;
    }

    startButton.addEventListener("click", startCamera);
    stopButton.addEventListener("click", stopCamera);
    window.addEventListener("beforeunload", stopCamera);
})();