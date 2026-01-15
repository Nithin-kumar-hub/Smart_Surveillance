/**
 * dashboard.js - FINAL VERSION WITH ALL FIXES
 * Includes: Detection count fix, Timezone fix, Alert sound, Analytics chart, No page blink
 * 
 * FIXES:
 * ✅ Issue 1: Analytics chart now works
 * ✅ Issue 2: Page doesn't blink on detection
 * ✅ Issue 3: Timezone fixed (IST)
 * ✅ Detection count accurate
 * ✅ Alert sound with beep
 */

// Configuration
const API_BASE = 'http://localhost:5000';
const SOCKET_URL = 'http://localhost:5000';

// Global state
let socket = null;
let cameras = [];
let alerts = [];
let alertSound = null;
let cameraViewManager = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    initializeApp();
});

/**
 * Initialize the application
 */
function initializeApp() {
    console.log('Initializing Smart Surveillance Dashboard...');

    // Initialize camera view manager
    cameraViewManager = new CameraViewManager(API_BASE);
    cameraViewManager.initialize('cameraGrid');

    // Initialize alert sound
    alertSound = document.getElementById('alertSound');

    // Connect to WebSocket
    connectSocket();

    // Load initial data
    loadCameras();
    loadAlerts();
    loadStatistics();

    // Start clock
    updateClock();
    setInterval(updateClock, 1000);

    // Refresh data periodically (faster polling since WebSocket may fail)
    setInterval(loadAlerts, 2000);  // Every 2 seconds (faster updates)
    setInterval(loadStatistics, 5000);  // Every 5 seconds
    setInterval(() => {
        if (cameraViewManager.getCameraCount() > 0) {
            cameraViewManager.refreshAllCameras();
        }
    }, 60000); // Every minute

    console.log('Application initialized successfully');
}

/**
 * Connect to WebSocket server
 */
function connectSocket() {
    socket = io(SOCKET_URL, {
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
        transports: ['websocket']
    });

    socket.on('connect', function () {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
    });

    socket.on('disconnect', function () {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
    });

    socket.on('new_alert', function (data) {
        console.log('🚨 NEW ALERT RECEIVED VIA WEBSOCKET:', data);
        console.log('Alert details:', {
            camera: data.camera_name,
            object: data.object_class,
            confidence: data.confidence,
            severity: data.severity
        });
        handleNewAlert(data);
    });

    socket.on('alert_acknowledged', function (data) {
        console.log('Alert acknowledged:', data);
        removeAlertFromUI(data.alert_id);
    });

    socket.on('camera_status_update', function (data) {
        console.log('Camera status update:', data);
        if (cameraViewManager) {
            cameraViewManager.updateCameraStatus(data.camera_id, data.status);
        }
    });

    socket.on('connection_response', function (data) {
        console.log('Connection response:', data);
    });

    socket.on('connect_error', function (error) {
        console.error('WebSocket connection error:', error);
        updateConnectionStatus(false);
    });
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connectionStatus');
    if (connected) {
        statusElement.innerHTML = '<i class="bi bi-wifi"></i> Connected';
        statusElement.className = 'badge bg-success me-3';
    } else {
        statusElement.innerHTML = '<i class="bi bi-wifi-off"></i> Disconnected';
        statusElement.className = 'badge bg-danger me-3';
    }
}

/**
 * Update clock display
 */
function updateClock() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-IN', {
        hour12: true,
        timeZone: 'Asia/Kolkata'
    });
    const dateString = now.toLocaleDateString('en-IN', {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        timeZone: 'Asia/Kolkata'
    });
    document.getElementById('currentTime').textContent = `${dateString} ${timeString}`;
}

/**
 * Load all cameras
 */
async function loadCameras() {
    try {
        showLoadingState();

        const response = await fetch(`${API_BASE}/api/cameras`);
        const data = await response.json();

        if (data.success) {
            cameras = data.cameras;
            renderCameras();
            updateActiveCamerasCount();
        } else {
            showNotification('Failed to load cameras', 'danger');
        }
    } catch (error) {
        console.error('Error loading cameras:', error);
        showNotification('Error connecting to server', 'danger');
        showErrorState();
    } finally {
        hideLoadingState();
    }
}

/**
 * Render camera grid
 */
function renderCameras() {
    const grid = document.getElementById('cameraGrid');

    if (cameras.length === 0) {
        grid.innerHTML = `
            <div class="no-cameras">
                <i class="bi bi-camera-video-off"></i>
                <h5>No Cameras Found</h5>
                <p>Add a camera to start monitoring</p>
                <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addCameraModal">
                    <i class="bi bi-plus-circle"></i> Add Camera
                </button>
            </div>
        `;
        return;
    }

    // Clear existing views
    cameraViewManager.clearAllCameras();

    // Add each camera
    cameras.forEach(camera => {
        cameraViewManager.addCamera(camera);
    });
}

/**
 * Load alerts
 */
async function loadAlerts() {
    try {
        const response = await fetch(`${API_BASE}/api/alerts?pending=true`);
        const data = await response.json();

        if (data.success) {
            const previousCount = alerts.length;
            const previousAlerts = JSON.stringify(alerts);
            alerts = data.alerts;
            const newCount = alerts.length;
            const currentAlerts = JSON.stringify(alerts);
            
            // Check if new alerts were added
            if (newCount > previousCount) {
                console.log(`🆕 New alerts detected! (${previousCount} → ${newCount})`);
                
                // Play sound for new alerts
                playAlertSound();
                
                // Show notification for newest alert
                if (alerts.length > 0) {
                    const newestAlert = alerts[0];
                    const message = `${newestAlert.object_class.toUpperCase()} detected at ${newestAlert.camera_name}`;
                    showNotification(message, 'danger');
                }
                
                // Only re-render if alerts actually changed
                renderAlerts();
                updateAlertCount();
            } else if (previousAlerts !== currentAlerts) {
                // Alerts changed but count is same (e.g., acknowledged)
                renderAlerts();
                updateAlertCount();
            } else {
                // No changes, just update count (no re-render to prevent blink)
                updateAlertCount();
            }
        }
    } catch (error) {
        console.error('Error loading alerts:', error);
    }
}

/**
 * Render alerts list (optimized to prevent blink)
 */
function renderAlerts() {
    const alertsList = document.getElementById('alertsList');

    if (alerts.length === 0) {
        if (alertsList.innerHTML.includes('No active alerts')) {
            return; // Already showing "no alerts", don't re-render
        }
        alertsList.innerHTML = '<p class="text-muted text-center py-3">No active alerts</p>';
        return;
    }

    // Build new HTML
    const newHTML = alerts.map(alert => `
        <div class="alert-item severity-${alert.severity}" id="alert-${alert.id}">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                    <strong>${escapeHtml(alert.camera_name)}</strong>
                    <span class="badge bg-${getSeverityColor(alert.severity)} ms-2">${alert.severity}</span>
                </div>
                <button class="btn btn-sm btn-success" onclick="acknowledgeAlert(${alert.id})" title="Acknowledge">
                    <i class="bi bi-check-lg"></i>
                </button>
            </div>
            <div class="mb-2">
                <i class="bi bi-exclamation-circle text-danger"></i>
                <strong>${escapeHtml(alert.object_class)}</strong> detected
                <small class="text-muted">(${(alert.confidence * 100).toFixed(1)}% confidence)</small>
            </div>
            <small class="text-muted d-block">
                <i class="bi bi-geo-alt"></i> ${escapeHtml(alert.location || 'Unknown location')}
            </small>
            <small class="text-muted d-block">
                <i class="bi bi-clock"></i> ${formatDateTime(alert.created_at)}
            </small>
        </div>
    `).join('');
    
    // Only update if content actually changed
    if (alertsList.innerHTML !== newHTML) {
        alertsList.innerHTML = newHTML;
    }
}

/**
 * Get severity color for badge
 */
function getSeverityColor(severity) {
    switch (severity) {
        case 'HIGH': return 'danger';
        case 'MEDIUM': return 'warning';
        case 'LOW': return 'info';
        default: return 'secondary';
    }
}

/**
 * Update alert count badge
 */
function updateAlertCount() {
    const count = alerts.length;
    document.getElementById('alertCount').textContent = count;

    // Update page title with alert count
    if (count > 0) {
        document.title = `(${count}) Smart Surveillance - Alerts`;
    } else {
        document.title = 'Smart Surveillance Dashboard';
    }
}

/**
 * Handle new alert from WebSocket - FIXED: No page reload
 */
function handleNewAlert(alertData) {
    console.log('📢 Processing new alert:', alertData);

    // Play alert sound (uses Web Audio API beep)
    console.log('🔊 Playing alert sound...');
    playAlertSound();

    // Show browser notification if supported
    showBrowserNotification(alertData);

    // Show toast notification
    const message = `${alertData.object_class.toUpperCase()} detected at ${alertData.camera_name} (${(alertData.confidence * 100).toFixed(1)}%)`;
    console.log('📣 Showing notification:', message);
    showNotification(message, 'danger');

    // Show visual alert on camera
    if (cameraViewManager) {
        cameraViewManager.showAlert(alertData.camera_id, alertData);
    }

    // FIXED: Only reload alerts and statistics, NOT cameras (prevents page blink)
    console.log('🔄 Reloading alerts and statistics...');
    loadAlerts();
    loadStatistics();
    
    console.log('✅ Alert handling complete');
}

/**
 * Play alert sound - Uses Web Audio API beep
 */
function playAlertSound() {
    try {
        // Create Web Audio API beep
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Configure beep sound
        oscillator.frequency.value = 800; // Frequency in Hz
        oscillator.type = 'sine';
        
        // Volume envelope
        gainNode.gain.setValueAtTime(0, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.3, audioContext.currentTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        // Play beep
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
        
        console.log('Alert sound played');
    } catch (e) {
        console.log('Could not play alert sound:', e);
        // Fallback: try HTML audio element
        try {
            const alertSound = document.getElementById('alertSound');
            if (alertSound) {
                alertSound.play().catch(err => console.log('HTML audio failed:', err));
            }
        } catch (err) {
            console.log('All audio methods failed');
        }
    }
}

/**
 * Play alert sound - Uses Web Audio API beep
 */
function playAlertSound() {
    try {
        // Create Web Audio API beep
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Configure beep sound
        oscillator.frequency.value = 800; // Frequency in Hz
        oscillator.type = 'sine';
        
        // Volume envelope
        gainNode.gain.setValueAtTime(0, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.3, audioContext.currentTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        // Play beep
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
        
        console.log('Alert sound played');
    } catch (e) {
        console.log('Could not play alert sound:', e);
        // Fallback: try HTML audio element
        try {
            if (alertSound) {
                alertSound.play().catch(err => console.log('HTML audio failed:', err));
            }
        } catch (err) {
            console.log('All audio methods failed');
        }
    }
}

/**
 * Show browser notification
 */
function showBrowserNotification(alertData) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Security Alert!', {
            body: `${alertData.object_class} detected at ${alertData.camera_name}`,
            icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="50" font-size="50">⚠️</text></svg>',
            badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="50" font-size="50">🚨</text></svg>',
            tag: `alert-${alertData.alert_id}`,
            requireInteraction: true
        });
    } else if ('Notification' in window && Notification.permission !== 'denied') {
        Notification.requestPermission();
    }
}

/**
 * Acknowledge an alert
 */
async function acknowledgeAlert(alertId) {
    try {
        const response = await fetch(`${API_BASE}/api/alerts/${alertId}/acknowledge`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                admin_name: 'Admin'
            })
        });

        const data = await response.json();

        if (data.success) {
            removeAlertFromUI(alertId);
            showNotification('Alert acknowledged', 'success');
        } else {
            showNotification(data.error || 'Failed to acknowledge alert', 'danger');
        }
    } catch (error) {
        console.error('Error acknowledging alert:', error);
        showNotification('Failed to acknowledge alert', 'danger');
    }
}

/**
 * Remove alert from UI with animation
 */
function removeAlertFromUI(alertId) {
    const alertElement = document.getElementById(`alert-${alertId}`);
    if (alertElement) {
        alertElement.style.transition = 'all 0.3s ease';
        alertElement.style.opacity = '0';
        alertElement.style.transform = 'translateX(-20px)';

        setTimeout(() => {
            alertElement.remove();
            alerts = alerts.filter(a => a.id !== alertId);
            updateAlertCount();

            if (alerts.length === 0) {
                renderAlerts();
            }
        }, 300);
    }
}

/**
 * Load statistics - FIXED: Display correct count
 */
async function loadStatistics() {
    try {
        const response = await fetch(`${API_BASE}/api/analytics/summary?hours=24`);
        const data = await response.json();

        if (data.success) {
            // Fix: Display actual count from database, default to 0 if undefined
            const count = data.summary.total_detections || 0;
            document.getElementById('totalDetections').textContent = count;
            updateActiveCamerasCount();
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
        document.getElementById('totalDetections').textContent = '0';
    }
}

/**
 * Update active cameras count
 */
function updateActiveCamerasCount() {
    const activeCount = cameras.filter(c => c.status === 'active').length;
    document.getElementById('activeCameras').textContent = activeCount;
}

/**
 * Load analytics with time range
 */
async function loadAnalytics(hours = 24) {
    try {
        // Update active button
        document.querySelectorAll('#analyticsModal .btn-group button').forEach(btn => {
            btn.classList.remove('active');
        });
        event?.target?.classList.add('active');

        // Load hourly data
        const hourlyResponse = await fetch(`${API_BASE}/api/analytics/hourly?hours=${hours}`);
        const hourlyData = await hourlyResponse.json();

        // Load summary data
        const summaryResponse = await fetch(`${API_BASE}/api/analytics/summary?hours=${hours}`);
        const summaryData = await summaryResponse.json();

        if (hourlyData.success && summaryData.success) {
            renderAnalyticsCharts(hourlyData.data, summaryData.summary, hours);
        } else {
            showNoDataMessage();
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
        showNotification('Failed to load analytics', 'danger');
    }
}

/**
 * Show analytics modal with chart (legacy function)
 */
async function showAnalytics() {
    loadAnalytics(24);
}

/**
 * Render all analytics charts
 */
function renderAnalyticsCharts(hourlyData, summaryData, hours) {
    // Update summary stats
    updateSummaryStats(summaryData, hourlyData);

    // Render main timeline chart
    renderTimelineChart(hourlyData, hours);

    // Render class distribution chart
    renderClassChart(summaryData.by_class);

    // Render camera distribution chart
    renderCameraChart(summaryData.by_camera);
}

/**
 * Update summary statistics
 */
function updateSummaryStats(summaryData, hourlyData) {
    // Total detections
    document.getElementById('totalDetectionsAnalytics').textContent = summaryData.total_detections || 0;

    // Most detected class
    if (summaryData.by_class && summaryData.by_class.length > 0) {
        document.getElementById('mostDetectedClass').textContent = 
            summaryData.by_class[0].object_class.toUpperCase();
    } else {
        document.getElementById('mostDetectedClass').textContent = '-';
    }

    // Peak hour
    if (hourlyData && hourlyData.length > 0) {
        const hourCounts = {};
        hourlyData.forEach(d => {
            hourCounts[d.hour] = (hourCounts[d.hour] || 0) + d.count;
        });
        const peakHour = Object.keys(hourCounts).reduce((a, b) => 
            hourCounts[a] > hourCounts[b] ? a : b
        );
        const date = new Date(peakHour);
        document.getElementById('peakHour').textContent = 
            date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' });
    } else {
        document.getElementById('peakHour').textContent = '-';
    }
}

/**
 * Render timeline chart
 */
function renderTimelineChart(data, hours) {
    const canvas = document.getElementById('analyticsChart');
    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (window.analyticsChartInstance) {
        window.analyticsChartInstance.destroy();
    }

    if (!data || data.length === 0) {
        showNoDataMessage();
        return;
    }

    // Prepare data
    const hoursSet = [...new Set(data.map(d => d.hour))];
    const classes = [...new Set(data.map(d => d.object_class))];

    const colors = [
        'rgba(231, 76, 60, 0.8)',   // Red
        'rgba(52, 152, 219, 0.8)',  // Blue
        'rgba(46, 204, 113, 0.8)',  // Green
        'rgba(241, 196, 15, 0.8)',  // Yellow
        'rgba(155, 89, 182, 0.8)',  // Purple
        'rgba(230, 126, 34, 0.8)'   // Orange
    ];

    const datasets = classes.map((className, index) => ({
        label: className.toUpperCase(),
        data: hoursSet.map(hour => {
            const entry = data.find(d => d.hour === hour && d.object_class === className);
            return entry ? entry.count : 0;
        }),
        backgroundColor: colors[index % colors.length],
        borderColor: colors[index % colors.length].replace('0.8', '1'),
        borderWidth: 2
    }));

    // Create chart
    window.analyticsChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hoursSet.map(h => {
                const date = new Date(h);
                return date.toLocaleTimeString('en-IN', {
                    hour: '2-digit',
                    minute: '2-digit',
                    timeZone: 'Asia/Kolkata'
                });
            }),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: `Harmful Tool Detections - Last ${hours} Hours`,
                    font: { size: 18, weight: 'bold' }
                },
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1, precision: 0 },
                    title: { display: true, text: 'Number of Detections' }
                },
                x: {
                    title: { display: true, text: 'Time (IST)' }
                }
            }
        }
    });
}

/**
 * Render class distribution chart
 */
function renderClassChart(byClass) {
    const canvas = document.getElementById('classChart');
    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (window.classChartInstance) {
        window.classChartInstance.destroy();
    }

    if (!byClass || byClass.length === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '14px Arial';
        ctx.fillStyle = '#999';
        ctx.textAlign = 'center';
        ctx.fillText('No data', canvas.width / 2, canvas.height / 2);
        return;
    }

    const colors = [
        'rgba(231, 76, 60, 0.8)',
        'rgba(52, 152, 219, 0.8)',
        'rgba(46, 204, 113, 0.8)',
        'rgba(241, 196, 15, 0.8)',
        'rgba(155, 89, 182, 0.8)',
        'rgba(230, 126, 34, 0.8)'
    ];

    window.classChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: byClass.map(c => c.object_class.toUpperCase()),
            datasets: [{
                data: byClass.map(c => c.count),
                backgroundColor: colors,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return `${context.label}: ${context.parsed} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render camera distribution chart
 */
function renderCameraChart(byCamera) {
    const canvas = document.getElementById('cameraChart');
    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (window.cameraChartInstance) {
        window.cameraChartInstance.destroy();
    }

    if (!byCamera || byCamera.length === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '14px Arial';
        ctx.fillStyle = '#999';
        ctx.textAlign = 'center';
        ctx.fillText('No data', canvas.width / 2, canvas.height / 2);
        return;
    }

    window.cameraChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: byCamera.map(c => c.name),
            datasets: [{
                label: 'Detections',
                data: byCamera.map(c => c.count),
                backgroundColor: 'rgba(52, 152, 219, 0.8)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { stepSize: 1, precision: 0 }
                }
            }
        }
    });
}

/**
 * Show no data message
 */
function showNoDataMessage() {
    const canvas = document.getElementById('analyticsChart');
    const ctx = canvas.getContext('2d');
    
    if (window.analyticsChartInstance) {
        window.analyticsChartInstance.destroy();
    }
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = '20px Arial';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText('No detection data available for selected time range', canvas.width / 2, canvas.height / 2);
    
    // Clear stats
    document.getElementById('totalDetectionsAnalytics').textContent = '0';
    document.getElementById('mostDetectedClass').textContent = '-';
    document.getElementById('peakHour').textContent = '-';
}

/**
 * Toggle camera source input based on type
 */
function toggleSourceInput() {
    const sourceType = document.getElementById('cameraSourceType').value;
    const rtspInput = document.getElementById('rtspUrlInput');
    const rtspField = document.getElementById('cameraRtsp');

    if (sourceType === 'webcam') {
        rtspInput.style.display = 'none';
        rtspField.value = '0';
        rtspField.required = false;
    } else {
        rtspInput.style.display = 'block';
        rtspField.value = '';
        rtspField.required = true;

        if (sourceType === 'rtsp') {
            rtspField.placeholder = 'rtsp://username:password@ip:port/stream';
        } else if (sourceType === 'video') {
            rtspField.placeholder = 'path/to/video.mp4';
        }
    }
}

/**
 * Add new camera
 */
async function addCamera() {
    const name = document.getElementById('cameraName').value.trim();
    const location = document.getElementById('cameraLocation').value.trim();
    const sourceType = document.getElementById('cameraSourceType').value;
    let rtspUrl = document.getElementById('cameraRtsp').value.trim();

    // Validation
    if (!name) {
        showNotification('Please enter camera name', 'warning');
        return;
    }

    if (sourceType === 'webcam') {
        rtspUrl = '0';
    } else if (!rtspUrl) {
        showNotification('Please enter camera source', 'warning');
        return;
    }

    try {
        showButtonLoading('addCameraBtn', true);

        const response = await fetch(`${API_BASE}/api/cameras`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                location: location,
                rtsp_url: rtspUrl
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification('Camera added successfully!', 'success');

            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('addCameraModal'));
            modal.hide();

            // Reset form
            document.getElementById('addCameraForm').reset();
            toggleSourceInput();

            // Reload cameras
            setTimeout(() => {
                loadCameras();
            }, 1000);
        } else {
            showNotification(data.error || 'Failed to add camera', 'danger');
        }
    } catch (error) {
        console.error('Error adding camera:', error);
        showNotification('Failed to add camera. Check your connection.', 'danger');
    } finally {
        showButtonLoading('addCameraBtn', false);
    }
}

/**
 * Remove camera
 */
async function removeCamera(cameraId) {
    if (!confirm('Are you sure you want to remove this camera?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/cameras/${cameraId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showNotification('Camera removed successfully', 'success');

            // Remove from view
            cameraViewManager.removeCamera(cameraId);
            cameras = cameras.filter(c => c.id !== cameraId);

        } else {
            showNotification(data.error || 'Failed to remove camera', 'danger');
        }
    } catch (error) {
        console.error('Error removing camera:', error);
        showNotification('Failed to remove camera', 'danger');
    }
}

/**
 * Refresh all camera feeds
 */
function refreshAllCameras() {
    if (cameraViewManager) {
        cameraViewManager.refreshAllCameras();
        showNotification('Refreshing all cameras...', 'info');
    }
    const grid = document.getElementById('cameraGrid');
    grid.innerHTML = `
        <div class="no-cameras">
            <i class="bi bi-exclamation-triangle text-danger"></i>
            <h5>Connection Error</h5>
            <p>Unable to connect to the server</p>
            <button class="btn btn-primary" onclick="loadCameras()">
                <i class="bi bi-arrow-clockwise"></i> Retry
            </button>
        </div>
    `;
}

/**
 * Show button loading state
 */
function showButtonLoading(buttonId, isLoading) {
    const button = document.getElementById(buttonId);
    if (!button) return;

    if (isLoading) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
    } else {
        button.disabled = false;
        button.innerHTML = 'Add Camera';
    }
}

/**
 * Show notification (Bootstrap toast)
 */
function showNotification(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '99999';
        document.body.appendChild(container);
    }

    // Icon based on type
    let icon = '';
    switch (type) {
        case 'success': icon = '<i class="bi bi-check-circle-fill me-2"></i>'; break;
        case 'danger': icon = '<i class="bi bi-exclamation-circle-fill me-2"></i>'; break;
        case 'warning': icon = '<i class="bi bi-exclamation-triangle-fill me-2"></i>'; break;
        case 'info': icon = '<i class="bi bi-info-circle-fill me-2"></i>'; break;
    }

    // Create toast
    const toastId = `toast-${Date.now()}`;
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${icon}${escapeHtml(message)}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    container.appendChild(toast);

    // Show toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: type === 'danger' ? 5000 : 3000
    });
    bsToast.show();

    // Remove after hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

/**
 * Format date time - FIXED for IST timezone
 */
function formatDateTime(dateString) {
    try {
        const date = new Date(dateString);
        const now = new Date();

        // Check if date is valid
        if (isNaN(date.getTime())) {
            return 'Invalid date';
        }

        const diff = now - date;

        // Less than 1 minute
        if (diff < 60000) {
            return 'Just now';
        }

        // Less than 1 hour
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        }

        // Less than 24 hours
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        }

        // Otherwise show full date and time in IST (Asia/Kolkata)
        return date.toLocaleString('en-IN', {
            timeZone: 'Asia/Kolkata',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        console.error('Error formatting date:', error);
        return 'Unknown time';
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show loading state in camera grid
 */
function showLoadingState() {
    const grid = document.getElementById('cameraGrid');
    grid.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 text-muted">Loading cameras...</p>
        </div>
    `;
}

/**
 * Hide loading state
 */
function hideLoadingState() {
    // Nothing to do, renderCameras will overwrite
}

/**
 * Show error state
 */
function showErrorState() {
    const grid = document.getElementById('cameraGrid');
    grid.innerHTML = `
        <div class="no-cameras">
            <i class="bi bi-exclamation-triangle text-danger"></i>
            <h5>Connection Error</h5>
            <p>Unable to connect to the server</p>
            <button class="btn btn-primary" onclick="loadCameras()">
                <i class="bi bi-arrow-clockwise"></i> Retry
            </button>
        </div>
    `;
}

/**
 * Request notification permission on load
 */
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

/**
 * Test alert system (for debugging)
 */
function testAlert() {
    console.log('🧪 Testing alert system...');
    const testAlertData = {
        alert_id: 999,
        camera_id: 4,
        camera_name: 'Test Camera',
        location: 'Test Location',
        object_class: 'knife',
        confidence: 0.95,
        severity: 'HIGH',
        timestamp: new Date().toISOString(),
        snapshot: 'test.jpg'
    };
    console.log('Test alert data:', testAlertData);
    handleNewAlert(testAlertData);
}

// Expose functions globally for HTML onclick handlers
window.addCamera = addCamera;
window.removeCamera = removeCamera;
window.acknowledgeAlert = acknowledgeAlert;
window.refreshAllCameras = refreshAllCameras;
window.toggleSourceInput = toggleSourceInput;
window.showAnalytics = showAnalytics;
window.loadAnalytics = loadAnalytics;
window.testAlert = testAlert;
window.cameraViewManager = cameraViewManager;