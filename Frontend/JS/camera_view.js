/**
 * camera-view.js
 * Camera feed management and visualization module
 * Place this file in: frontend/js/camera-view.js
 */

/**
 * CameraView Class
 * Manages individual camera display and interactions
 */
class CameraView {
    constructor(camera, apiBase) {
        this.camera = camera;
        this.apiBase = apiBase;
        this.streamUrl = `${apiBase}/api/cameras/${camera.id}/stream`;
        this.element = null;
        this.imgElement = null;
        this.isFullscreen = false;
        this.streamActive = false;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.retryDelay = 2000;
    }

    /**
     * Create camera card HTML element
     */
    createElement() {
        const card = document.createElement('div');
        card.className = 'camera-card';
        card.id = `camera-${this.camera.id}`;
        card.innerHTML = this.getCardHTML();
        
        this.element = card;
        this.attachEventListeners();
        
        return card;
    }

    /**
     * Generate camera card HTML
     */
    getCardHTML() {
        const statusClass = this.camera.status === 'active' ? 'badge-online' : 'badge-offline';
        const statusText = this.camera.status === 'active' ? 'ONLINE' : 'OFFLINE';
        
        return `
            <div class="camera-header">
                <div>
                    <h6 class="mb-0">${this.escapeHtml(this.camera.name)}</h6>
                    <small>${this.escapeHtml(this.camera.location || 'No location')}</small>
                </div>
                <div>
                    <span class="badge-status ${statusClass}" id="status-${this.camera.id}">
                        ${statusText}
                    </span>
                </div>
            </div>
            <div class="camera-feed" id="feed-${this.camera.id}">
                <img src="${this.streamUrl}?t=${Date.now()}" 
                     alt="${this.escapeHtml(this.camera.name)}"
                     loading="lazy"
                     onerror="cameraViewManager.handleImageError(${this.camera.id})">
                <div class="camera-controls">
                    <button class="btn btn-sm btn-light" onclick="cameraViewManager.toggleFullscreen(${this.camera.id})" title="Fullscreen">
                        <i class="bi bi-arrows-fullscreen"></i>
                    </button>
                    <button class="btn btn-sm btn-light" onclick="cameraViewManager.refreshCamera(${this.camera.id})" title="Refresh">
                        <i class="bi bi-arrow-clockwise"></i>
                    </button>
                    <button class="btn btn-sm btn-light" onclick="cameraViewManager.takeSnapshot(${this.camera.id})" title="Snapshot">
                        <i class="bi bi-camera"></i>
                    </button>
                </div>
            </div>
            <div class="camera-status">
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-muted">
                        <i class="bi bi-eye-fill"></i> Camera ID: ${this.camera.id}
                        <span id="fps-${this.camera.id}" class="ms-2"></span>
                    </small>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-info" 
                                onclick="cameraViewManager.showCameraInfo(${this.camera.id})"
                                title="Info">
                            <i class="bi bi-info-circle"></i>
                        </button>
                        <button class="btn btn-outline-warning" 
                                onclick="cameraViewManager.toggleCamera(${this.camera.id})"
                                title="Start/Stop">
                            <i class="bi bi-pause-circle"></i>
                        </button>
                        <button class="btn btn-outline-danger" 
                                onclick="cameraViewManager.confirmRemoveCamera(${this.camera.id})"
                                title="Remove">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners to camera elements
     */
    attachEventListeners() {
        const img = this.element.querySelector('img');
        
        if (img) {
            this.imgElement = img;
            
            img.addEventListener('load', () => {
                this.streamActive = true;
                this.retryCount = 0;
                this.hideLoadingState();
            });
            
            img.addEventListener('error', () => {
                this.handleStreamError();
            });
            
            // Double-click for fullscreen
            img.addEventListener('dblclick', () => {
                this.toggleFullscreen();
            });
        }
    }

    /**
     * Handle stream error
     */
    handleStreamError() {
        this.streamActive = false;
        
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            console.log(`Camera ${this.camera.id}: Retry ${this.retryCount}/${this.maxRetries}`);
            
            setTimeout(() => {
                this.refreshStream();
            }, this.retryDelay);
        } else {
            this.showOfflineState();
        }
    }

    /**
     * Show offline state
     */
    showOfflineState() {
        const feed = this.element.querySelector('.camera-feed');
        if (feed) {
            feed.innerHTML = `
                <div class="camera-offline">
                    <i class="bi bi-camera-video-off"></i>
                    <div>Camera Offline</div>
                    <button class="btn btn-sm btn-outline-light" onclick="cameraViewManager.refreshCamera(${this.camera.id})">
                        <i class="bi bi-arrow-clockwise"></i> Retry
                    </button>
                </div>
            `;
        }
        
        this.updateStatus('offline');
    }

    /**
     * Show loading state
     */
    showLoadingState() {
        const feed = this.element.querySelector('.camera-feed');
        if (feed) {
            feed.classList.add('loading');
        }
    }

    /**
     * Hide loading state
     */
    hideLoadingState() {
        const feed = this.element.querySelector('.camera-feed');
        if (feed) {
            feed.classList.remove('loading');
        }
    }

    /**
     * Refresh camera stream
     */
    refreshStream() {
        if (this.imgElement) {
            const timestamp = Date.now();
            this.imgElement.src = `${this.streamUrl}?t=${timestamp}`;
            this.showLoadingState();
        }
    }

    /**
     * Update camera status
     */
    updateStatus(status) {
        const statusBadge = document.getElementById(`status-${this.camera.id}`);
        if (statusBadge) {
            statusBadge.className = status === 'active' || status === 'online' 
                ? 'badge-status badge-online' 
                : 'badge-status badge-offline';
            statusBadge.textContent = status === 'active' || status === 'online' 
                ? 'ONLINE' 
                : 'OFFLINE';
        }
    }

    /**
     * Show alert badge on camera
     */
    showAlert(alertData) {
        const feed = this.element.querySelector('.camera-feed');
        if (!feed) return;
        
        // Remove existing alert badge if any
        const existingBadge = feed.querySelector('.alert-badge');
        if (existingBadge) {
            existingBadge.remove();
        }
        
        // Create new alert badge
        const badge = document.createElement('div');
        badge.className = 'alert-badge';
        badge.textContent = `⚠ ${alertData.object_class.toUpperCase()}`;
        feed.appendChild(badge);
        
        // Flash the camera feed
        feed.style.border = '3px solid var(--danger-color)';
        setTimeout(() => {
            feed.style.border = 'none';
        }, 500);
        
        // Remove badge after 5 seconds
        setTimeout(() => {
            badge.remove();
        }, 5000);
    }

    /**
     * Toggle fullscreen
     */
    toggleFullscreen() {
        const feed = this.element.querySelector('.camera-feed');
        if (!feed) return;
        
        if (!this.isFullscreen) {
            if (feed.requestFullscreen) {
                feed.requestFullscreen();
            } else if (feed.webkitRequestFullscreen) {
                feed.webkitRequestFullscreen();
            } else if (feed.msRequestFullscreen) {
                feed.msRequestFullscreen();
            }
            this.isFullscreen = true;
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
            this.isFullscreen = false;
        }
    }

    /**
     * Take snapshot
     */
    async takeSnapshot() {
        if (!this.imgElement || !this.streamActive) {
            alert('Camera is not active');
            return;
        }
        
        try {
            // Create canvas from current image
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = this.imgElement.naturalWidth;
            canvas.height = this.imgElement.naturalHeight;
            
            ctx.drawImage(this.imgElement, 0, 0);
            
            // Convert to blob and download
            canvas.toBlob((blob) => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `camera_${this.camera.id}_${Date.now()}.jpg`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }, 'image/jpeg', 0.95);
            
            // Visual feedback
            this.flashCamera();
            
        } catch (error) {
            console.error('Failed to take snapshot:', error);
            alert('Failed to take snapshot');
        }
    }

    /**
     * Flash camera (snapshot effect)
     */
    flashCamera() {
        const feed = this.element.querySelector('.camera-feed');
        if (!feed) return;
        
        feed.style.filter = 'brightness(1.5)';
        setTimeout(() => {
            feed.style.filter = 'brightness(1)';
        }, 200);
    }

    /**
     * Update FPS display
     */
    updateFPS(fps) {
        const fpsElement = document.getElementById(`fps-${this.camera.id}`);
        if (fpsElement) {
            fpsElement.innerHTML = `<i class="bi bi-speedometer2"></i> ${fps.toFixed(1)} FPS`;
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Destroy camera view
     */
    destroy() {
        if (this.element) {
            this.element.remove();
        }
        this.imgElement = null;
        this.element = null;
    }
}


/**
 * CameraViewManager Class
 * Manages all camera views
 */
class CameraViewManager {
    constructor(apiBase) {
        this.apiBase = apiBase;
        this.cameraViews = new Map();
        this.gridContainer = null;
    }

    /**
     * Initialize manager
     */
    initialize(gridContainerId) {
        this.gridContainer = document.getElementById(gridContainerId);
        if (!this.gridContainer) {
            console.error('Camera grid container not found');
        }
    }

    /**
     * Add camera view
     */
    addCamera(camera) {
        if (this.cameraViews.has(camera.id)) {
            console.warn(`Camera ${camera.id} already exists`);
            return;
        }
        
        const cameraView = new CameraView(camera, this.apiBase);
        const element = cameraView.createElement();
        
        this.cameraViews.set(camera.id, cameraView);
        
        if (this.gridContainer) {
            this.gridContainer.appendChild(element);
        }
        
        return cameraView;
    }

    /**
     * Remove camera view
     */
    removeCamera(cameraId) {
        const cameraView = this.cameraViews.get(cameraId);
        if (cameraView) {
            cameraView.destroy();
            this.cameraViews.delete(cameraId);
        }
    }

    /**
     * Get camera view
     */
    getCamera(cameraId) {
        return this.cameraViews.get(cameraId);
    }

    /**
     * Refresh camera stream
     */
    refreshCamera(cameraId) {
        const cameraView = this.cameraViews.get(cameraId);
        if (cameraView) {
            cameraView.refreshStream();
        }
    }

    /**
     * Refresh all cameras
     */
    refreshAllCameras() {
        this.cameraViews.forEach(cameraView => {
            cameraView.refreshStream();
        });
    }

    /**
     * Handle image error (called from HTML)
     */
    handleImageError(cameraId) {
        const cameraView = this.cameraViews.get(cameraId);
        if (cameraView) {
            cameraView.handleStreamError();
        }
    }

    /**
     * Toggle fullscreen
     */
    toggleFullscreen(cameraId) {
        const cameraView = this.cameraViews.get(cameraId);
        if (cameraView) {
            cameraView.toggleFullscreen();
        }
    }

    /**
     * Take snapshot
     */
    takeSnapshot(cameraId) {
        const cameraView = this.cameraViews.get(cameraId);
        if (cameraView) {
            cameraView.takeSnapshot();
        }
    }

    /**
     * Show camera info
     */
    showCameraInfo(cameraId) {
        const cameraView = this.cameraViews.get(cameraId);
        if (!cameraView) return;
        
        const camera = cameraView.camera;
        const info = `
Camera Information:

ID: ${camera.id}
Name: ${camera.name}
Location: ${camera.location || 'Not specified'}
Status: ${camera.status}
Source: ${camera.rtsp_url}
Created: ${new Date(camera.created_at).toLocaleString()}
        `.trim();
        
        alert(info);
    }

    /**
     * Toggle camera (start/stop)
     */
    async toggleCamera(cameraId) {
        try {
            const response = await fetch(`${this.apiBase}/api/cameras/${cameraId}/toggle`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: 'toggle'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log(`Camera ${cameraId} toggled`);
                this.refreshCamera(cameraId);
            }
        } catch (error) {
            console.error('Failed to toggle camera:', error);
        }
    }

    /**
     * Confirm remove camera
     */
    confirmRemoveCamera(cameraId) {
        const cameraView = this.cameraViews.get(cameraId);
        if (!cameraView) return;
        
        const confirmed = confirm(`Remove camera "${cameraView.camera.name}"?`);
        if (confirmed) {
            // Call the remove function from dashboard.js
            if (typeof removeCamera === 'function') {
                removeCamera(cameraId);
            }
        }
    }

    /**
     * Show alert on camera
     */
    showAlert(cameraId, alertData) {
        const cameraView = this.cameraViews.get(cameraId);
        if (cameraView) {
            cameraView.showAlert(alertData);
        }
    }

    /**
     * Update camera status
     */
    updateCameraStatus(cameraId, status) {
        const cameraView = this.cameraViews.get(cameraId);
        if (cameraView) {
            cameraView.updateStatus(status);
        }
    }

    /**
     * Clear all cameras
     */
    clearAllCameras() {
        this.cameraViews.forEach(cameraView => {
            cameraView.destroy();
        });
        this.cameraViews.clear();
        
        if (this.gridContainer) {
            this.gridContainer.innerHTML = '';
        }
    }

    /**
     * Get all camera IDs
     */
    getCameraIds() {
        return Array.from(this.cameraViews.keys());
    }

    /**
     * Get camera count
     */
    getCameraCount() {
        return this.cameraViews.size;
    }
}

// Make classes available globally
window.CameraView = CameraView;
window.CameraViewManager = CameraViewManager;

// Export for use in other modules (if using module system)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CameraView, CameraViewManager };
}