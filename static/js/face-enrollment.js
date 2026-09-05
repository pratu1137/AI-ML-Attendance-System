(() => {
    const video = document.getElementById("enrollment-camera");
    const student = document.getElementById("student");
    const consent = document.getElementById("consent");
    const status = document.getElementById("enrollment-status");
    const sampleCount = document.getElementById("sample-count");
    const startButton = document.getElementById("start-enrollment");
    const captureButton = document.getElementById("capture-sample");
    const submitButton = document.getElementById("submit-enrollment");
    const fileInput = document.getElementById("face-files");
    const csrfToken = document.getElementById("csrf-token").value;
    const canvas = document.createElement("canvas");
    const samples = [];
    let stream = null;

    function updateControls() {
        const uploadedCount = Math.min(fileInput.files.length, 3 - samples.length);
        const totalSamples = samples.length + uploadedCount;
        captureButton.disabled = !stream || !student.value || !consent.checked || totalSamples >= 3;
        submitButton.disabled = totalSamples < 3 || !student.value || !consent.checked;
        sampleCount.textContent = `Samples: ${totalSamples} / 3`;
    }

    async function startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            status.textContent = "ERROR: BROWSER UNSUPPORTED";
            return;
        }
        status.textContent = "REQUESTING PERMISSION";
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
            video.srcObject = stream;
            await video.play();
            status.textContent = "ACTIVE: CAPTURE THREE SAMPLES";
            startButton.disabled = true;
            updateControls();
        } catch (error) {
            status.textContent = error.name === "NotAllowedError" ? "ERROR: PERMISSION DENIED" : "ERROR: CAMERA UNAVAILABLE";
        }
    }

    function captureSample() {
        canvas.width = Math.min(video.videoWidth, 960);
        canvas.height = Math.round(canvas.width * video.videoHeight / video.videoWidth);
        canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((blob) => {
            if (blob) samples.push(blob);
            updateControls();
        }, "image/jpeg", 0.9);
    }

    async function submitEnrollment() {
        submitButton.disabled = true;
        const formData = new FormData();
        formData.append("student_id", student.value);
        formData.append("consent", "true");
        samples.forEach((sample, index) => formData.append("samples", sample, `enrollment-${index + 1}.jpg`));
        Array.from(fileInput.files).slice(0, 3 - samples.length).forEach((sample) => formData.append("samples", sample, sample.name));
        try {
            const response = await fetch("/api/face/enroll", { method: "POST", headers: { "X-CSRFToken": csrfToken }, body: formData });
            const payload = await response.json();
            if (!response.ok || !payload.success) throw new Error(payload.error || "Enrollment failed.");
            status.textContent = "ENROLLMENT COMPLETE";
            samples.length = 0;
            updateControls();
        } catch (error) {
            status.textContent = error.message || "Enrollment request failed.";
            updateControls();
        }
    }

    student.addEventListener("change", updateControls);
    consent.addEventListener("change", updateControls);
    startButton.addEventListener("click", startCamera);
    captureButton.addEventListener("click", captureSample);
    submitButton.addEventListener("click", submitEnrollment);
    fileInput.addEventListener("change", updateControls);
    window.addEventListener("beforeunload", () => stream?.getTracks().forEach((track) => track.stop()));
})();