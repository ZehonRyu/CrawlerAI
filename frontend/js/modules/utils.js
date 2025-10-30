// frontend/js/modules/utils.js
function getCurrentPlatform() {
    const platformElement = document.getElementById('platform');
    if (platformElement) {
        return platformElement.value;
    }
}

export { getCurrentPlatform };
