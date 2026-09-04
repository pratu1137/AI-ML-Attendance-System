(() => {
    const video = document.getElementById("camera");
    const overlay = document.getElementById("face-overlay");
    const status = document.getElementById("camera-status");
    const result = document.getElementById("detection-result");
    const startButton = document.getElementById("start-camera");
    const stopButton = document.getElementById("stop-camera");
    const csrfToken = document.getElementById("csrf-token").value;
    const captureCanvas = document.createElement("canvas");
    const frameIntervalMs = 1000;
    let stream = null;
    let timer = null;
    let requestInFlight = false;

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
        const context = overlay.getContext("2d");
        context.clearRect(0, 0, overlay.width, overlay.height);
        context.strokeStyle = "#20c997";
        context.lineWidth = Math.max(2, overlay.width / 320);
        faces.forEach((face) => context.strokeRect(face.x, face.y, face.width, face.height));
    }

    async function processFrame() {
        if (requestInFlight || !stream || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
        requestInFlight = true;
        captureCanvas.width = Math.min(video.videoWidth, 960);
        captureCanvas.height = Math.round(captureCanvas.width * video.videoHeight / video.videoWidth);
        captureCanvas.getContext("2d").drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
        try {
            const blob = await new Promise((resolve) => captureCanvas.toBlob(resolve, "image/jpeg", 0.8));
            const formData = new FormData();
            formData.append("frame", blob, "camera-frame.jpg");
            const response = await fetch("/api/attendance/mark", {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: formData,
            });
            const payload = await response.json();
            if (!response.ok || !payload.success) throw new Error(payload.error || "Detection request failed.");
            drawFaces(payload.faces);
            if (payload.recorded) {
                result.textContent = `${payload.message} (${payload.attendance.status})`;
            } else if (payload.reason === "NO_FACE") {
                result.textContent = "No face detected.";
            } else if (payload.reason === "MULTIPLE_FACES") {
                result.textContent = "Multiple faces detected.";
            } else if (payload.reason === "ALREADY_RECORDED") {
                result.textContent = payload.message;
            } else if (payload.reason === "NO_ACTIVE_LECTURE") {
                result.textContent = "NO ACTIVE LECTURE";
            } else {
                result.textContent = "UNKNOWN PERSON";
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
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
            video.srcObject = stream;
            await video.play();
            setStatus("ACTIVE");
            startButton.disabled = true;
            stopButton.disabled = false;
            timer = window.setInterval(processFrame, frameIntervalMs);
        } catch (error) {
            setStatus(error.name === "NotAllowedError" ? "ERROR: PERMISSION DENIED" : "ERROR: CAMERA UNAVAILABLE");
            stream = null;
        }
    }

    function stopCamera() {
        if (timer) window.clearInterval(timer);
        timer = null;
        if (stream) stream.getTracks().forEach((track) => track.stop());
        stream = null;
        video.srcObject = null;
        clearOverlay();
        setStatus("OFFLINE");
        startButton.disabled = false;
        stopButton.disabled = true;
    }

    startButton.addEventListener("click", startCamera);
    stopButton.addEventListener("click", stopCamera);
    window.addEventListener("beforeunload", stopCamera);
})();