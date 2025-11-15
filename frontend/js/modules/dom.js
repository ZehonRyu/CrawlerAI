// frontend/js/modules/dom.js
let elements = {};

function initializeElements() {
    elements = {
        taskTypeSelect: document.getElementById('task-type'),
        configSection: document.getElementById('config-section'),
        dynamicConfig: document.getElementById('dynamic-config'),
        runBtn: document.getElementById('run-btn'),
        runStatus: document.getElementById('run-status'),
        resultSection: document.getElementById('result-section'),
        summarizeBtn: document.getElementById('summarize-btn'),
        summaryResult: document.getElementById('summary-result'),
        qaSection: document.getElementById('qa-section'),
        qaBtn: document.getElementById('qa-btn'),
        qaInput: document.getElementById('qa-input'),
        qaSubmit: document.getElementById('qa-submit'),
        qaHistory: document.getElementById('qa-history'),
        qrcodeSection: document.getElementById('qrcode-section'),
        qrcodeImage: document.getElementById('qrcode-image'),
        qrcodeMessage: document.getElementById('qrcode-message'),
        downloadSection: document.getElementById('download-section'),
        downloadSimpleBtn: document.getElementById('download-simple-btn'),
        downloadFullBtn: document.getElementById('download-full-btn'),
        // 上传文件相关元素
        platformType: document.getElementById('platform-type'),
        modelFile: document.getElementById('model-file'),
        uploadModelBtn: document.getElementById('upload-model-btn'),
        uploadModelStatus: document.getElementById('upload-model-status')
    };
    return elements;
}

function showElement(element) {
    if (element) {
        element.classList.remove('hidden');
        // 确保元素是可见的
        element.style.display = 'block';
    }
}

function hideElement(element) {
    if (element) {
        element.classList.add('hidden');
        // 确保元素是隐藏的
        element.style.display = 'none';
    }
}

function updateStatus(element, message, isError = false) {
    if (element) {
        element.innerHTML = message;
        element.classList.remove('hidden');
        if (isError) {
            element.classList.remove('status-info');
            element.classList.add('status-error');
        } else {
            element.classList.remove('status-error');
            element.classList.add('status-info');
        }
    }
}

export { initializeElements, showElement, hideElement, updateStatus, elements };
