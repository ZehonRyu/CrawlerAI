// frontend/js/main.js
import { getTaskConfig } from './modules/config.js';
import { initializeElements, showElement, hideElement, updateStatus, elements } from './modules/dom.js';
import { ApiClient } from './modules/api.js';
import { getCurrentPlatform } from './modules/utils.js';

// 当前选择的任务类型和任务ID
let currentTaskType = '';
let currentTaskId = '';

// 防止重复点击的标志
let isSummarizing = false;
let isAsking = false;
let isBuildingModel = false;
let isUploadingModel = false;

// 任务轮询间隔
const POLLING_INTERVAL = 2000; // 2秒

// 初始化应用
document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    attachEventListeners();
});

// 绑定事件监听器
function attachEventListeners() {
    if (elements.taskTypeSelect) {
        elements.taskTypeSelect.addEventListener('change', handleTaskTypeChange);
    }
    if (elements.runBtn) {
        elements.runBtn.addEventListener('click', runCrawler);
    }
    if (elements.summarizeBtn) {
        elements.summarizeBtn.addEventListener('click', summarizeContent);
    }
    if (elements.qaBtn) {
        elements.qaBtn.addEventListener('click', toggleQASection);
    }
    if (elements.qaSubmit) {
        elements.qaSubmit.addEventListener('click', askQuestion);
    }
    if (elements.qaInput) {
        elements.qaInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') askQuestion();
        });
    }
    if (elements.downloadBtn) {
        elements.downloadBtn.addEventListener('click', downloadResult);
    }
    // 新增事件监听器
    if (elements.buildModelBtn) {
        elements.buildModelBtn.addEventListener('click', buildModel);
    }
    // 上传文件并构建模型的事件监听器
    if (elements.uploadModelBtn) {
        elements.uploadModelBtn.addEventListener('click', uploadAndBuildModel);
    }
}

// 处理任务类型变化
function handleTaskTypeChange() {
    currentTaskType = elements.taskTypeSelect ? elements.taskTypeSelect.value : '';
    const config = getTaskConfig(currentTaskType);

    if (currentTaskType && config && elements.configSection && elements.dynamicConfig) {
        showElement(elements.configSection);
        renderDynamicConfig(config);
        if (elements.runBtn) {
            elements.runBtn.disabled = false;
        }
    } else if (elements.configSection && elements.runBtn) {
        hideElement(elements.configSection);
        elements.runBtn.disabled = true;
    }
}

// 渲染动态配置表单
function renderDynamicConfig(config) {
    if (!elements.dynamicConfig) return;

    elements.dynamicConfig.innerHTML = '';

    for (const [key, field] of Object.entries(config)) {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';

        if (field.type === 'hidden') {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.id = key;
            input.value = field.value;
            formGroup.appendChild(input);
        } else {
            const label = document.createElement('label');
            label.textContent = field.label + ':';
            label.setAttribute('for', key);
            formGroup.appendChild(label);

            if (field.type === 'select') {
                const select = document.createElement('select');
                select.id = key;
                field.options.forEach(option => {
                    const optionEl = document.createElement('option');
                    optionEl.value = option;
                    optionEl.textContent = option;
                    select.appendChild(optionEl);
                });
                formGroup.appendChild(select);
            } else {
                const input = document.createElement('input');
                input.type = field.type || 'text';
                input.id = key;
                input.placeholder = field.placeholder || '';
                input.value = field.value || '';
                formGroup.appendChild(input);
            }
        }

        elements.dynamicConfig.appendChild(formGroup);
    }
}

// 运行爬虫
async function runCrawler() {
    if (!elements.runBtn || !elements.runStatus) return;

    const config = collectFormData();
    if (!config) return;

    elements.runBtn.disabled = true;
    elements.runBtn.textContent = '运行中...';
    updateStatus(elements.runStatus, '<span class="loading"></span>正在启动任务...');

    try {
        const result = await ApiClient.runCrawler(config);

        if (result.success) {
            currentTaskId = result.task_id;
            updateStatus(elements.runStatus, '✅ ' + result.message);

            // 启动任务状态轮询
            startTaskPolling(currentTaskId);

            // 启动心跳检测
            startHeartbeat(currentTaskId);
        } else {
            throw new Error(result.message || '任务启动失败');
        }
    } catch (error) {
        updateStatus(elements.runStatus, '❌ ' + error.message, true);
        elements.runBtn.disabled = false;
        elements.runBtn.textContent = '运行爬虫和生成模型';
    }
}

// 收集表单数据
function collectFormData() {
    const taskType = elements.taskTypeSelect ? elements.taskTypeSelect.value : '';
    if (!taskType) {
        alert('请选择任务类型');
        return null;
    }

    const config = getTaskConfig(taskType);
    if (!config) {
        alert('无效的任务类型');
        return null;
    }

    const formData = {
        'task-type': taskType,
        'task_id': generateTaskId()
    };

    for (const [key, field] of Object.entries(config)) {
        const element = document.getElementById(key);
        if (element) {
            formData[key] = element.value;
        } else if (field.type === 'hidden' && field.value) {
            formData[key] = field.value;
        }
    }

    return formData;
}

// 生成任务ID
function generateTaskId() {
    return 'task_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

let pollingIntervalId = null;
let heartbeatIntervalId = null;

// 启动任务状态轮询
async function startTaskPolling(taskId) {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
    }

    pollingIntervalId = setInterval(async () => {
        try {
            const result = await ApiClient.getTaskStatus(taskId);

            if (result.status === 'completed') {
                clearInterval(pollingIntervalId);
                stopHeartbeat();
                handleTaskCompleted(result);
            } else if (result.status === 'error') {
                clearInterval(pollingIntervalId);
                stopHeartbeat();
                handleTaskError(result);
            } else if (result.status === 'cancelled') {
                clearInterval(pollingIntervalId);
                stopHeartbeat();
                handleTaskCancelled(result);
            } else {
                // 任务仍在运行中
                if (elements.runStatus) {
                    const message = result.message || '任务正在运行中...';
                    updateStatus(elements.runStatus, `<span class="loading"></span>${message}`);
                }

                // 处理二维码显示
                if (result.status === 'waiting_for_qr_code') {
                    await handleQRCodeDisplay(taskId);
                }
            }
        } catch (error) {
            console.error('轮询任务状态失败:', error);
        }
    }, 2000); // 每2秒轮询一次
}

// 处理任务完成
function handleTaskCompleted(result) {
    if (elements.runStatus) {
        updateStatus(elements.runStatus, '✅ 爬虫运行完成，请点击生成模型按钮生成模型');
    }

    if (elements.runBtn) {
        elements.runBtn.disabled = false;
        elements.runBtn.textContent = '运行爬虫和生成模型';
    }

    // 显示生成模型按钮
    if (elements.buildModelSection) {
        showElement(elements.buildModelSection);
    }

    // 显示下载按钮
    if (elements.downloadSection) {
        showElement(elements.downloadSection);
    }
}

// 处理任务错误
function handleTaskError(result) {
    if (elements.runStatus) {
        updateStatus(elements.runStatus, '❌ ' + (result.message || '任务执行失败'), true);
    }

    if (elements.runBtn) {
        elements.runBtn.disabled = false;
        elements.runBtn.textContent = '运行爬虫和生成模型';
    }
}

// 处理任务取消
function handleTaskCancelled(result) {
    if (elements.runStatus) {
        updateStatus(elements.runStatus, '⚠️ ' + (result.message || '任务已被取消'));
    }

    if (elements.runBtn) {
        elements.runBtn.disabled = false;
        elements.runBtn.textContent = '运行爬虫和生成模型';
    }
}

// 处理二维码显示
async function handleQRCodeDisplay(taskId) {
    try {
        const result = await ApiClient.getQrCode(taskId);
        if (result.success && result.qrcode) {
            if (elements.qrcodeSection) {
                showElement(elements.qrcodeSection);
            }
            if (elements.qrcodeImage) {
                elements.qrcodeImage.src = result.qrcode;
                elements.qrcodeImage.style.display = 'block';
            }
            if (elements.qrcodeMessage) {
                elements.qrcodeMessage.textContent = '请使用手机扫描二维码进行登录';
            }
        }
    } catch (error) {
        console.error('获取二维码失败:', error);
        if (elements.qrcodeMessage) {
            elements.qrcodeMessage.textContent = '二维码获取失败: ' + error.message;
        }
    }
}

// 启动心跳检测
function startHeartbeat(taskId) {
    if (heartbeatIntervalId) {
        clearInterval(heartbeatIntervalId);
    }

    heartbeatIntervalId = setInterval(async () => {
        try {
            await ApiClient.sendHeartbeat(taskId);
            console.log('心跳发送成功 - 任务ID: ' + taskId);
        } catch (error) {
            console.error('发送心跳失败:', error);
        }
    }, 10000); // 每10秒发送一次心跳
}

// 停止心跳检测
function stopHeartbeat() {
    if (heartbeatIntervalId) {
        console.log('停止心跳检测');
        clearInterval(heartbeatIntervalId);
        heartbeatIntervalId = null;
    }
}


// 在页面卸载时发送取消任务请求
window.addEventListener('beforeunload', function() {
    if (currentTaskId) {
        // 尝试取消任务
        ApiClient.cancelTask(currentTaskId).catch(() => {
            // 忽略错误，因为页面正在卸载
        });
    }
    // 停止心跳检测
    stopHeartbeat();
});


// 生成模型
async function buildModel() {
    if (isBuildingModel) {
        alert('模型生成已在进行中，请稍候...');
        return;
    }

    if (!currentTaskId) {
        alert('没有可生成模型的任务');
        return;
    }

    isBuildingModel = true;

    if (elements.buildModelBtn) {
        elements.buildModelBtn.disabled = true;
        elements.buildModelBtn.textContent = '生成中...';
    }

    if (elements.buildModelStatus) {
        updateStatus(elements.buildModelStatus, '<span class="loading"></span>正在提交模型构建任务...');
    }

    try {
        const result = await ApiClient.buildModel(currentTaskId);

        if (result.success) {
            if (elements.buildModelStatus) {
                updateStatus(elements.buildModelStatus, '<span class="loading"></span>模型构建任务已提交，正在处理中...');
            }

            // 启动模型构建任务状态轮询
            startBuildModelPolling(result.task_id);
        } else {
            throw new Error(result.message || '提交模型构建任务失败');
        }
    } catch (error) {
        if (elements.buildModelStatus) {
            updateStatus(elements.buildModelStatus, '❌ 提交模型构建任务出错: ' + error.message, true);
        }
        isBuildingModel = false;
        if (elements.buildModelBtn) {
            elements.buildModelBtn.disabled = false;
            elements.buildModelBtn.textContent = '生成模型';
        }
    }
}

// 启动模型构建任务状态轮询
async function startBuildModelPolling(taskId) {
    console.log('开始轮询模型构建任务状态，任务ID:', taskId); // 添加调试日志
    const pollingInterval = setInterval(async () => {
        try {
            const result = await ApiClient.getBuildModelStatus(taskId);
            console.log('模型构建任务状态轮询结果:', result); // 添加调试日志

            if (result.state === 'SUCCESS') {
                console.log('模型构建任务成功完成'); // 添加调试日志
                clearInterval(pollingInterval);
                if (elements.buildModelStatus) {
                    updateStatus(elements.buildModelStatus, '✅ ' + result.result.message);
                }
                // 显示结果区域和下载区域
                if (elements.resultSection) {
                    showElement(elements.resultSection);
                }
                if (elements.downloadSection) {
                    showElement(elements.downloadSection);
                }
                isBuildingModel = false;
                if (elements.buildModelBtn) {
                    elements.buildModelBtn.disabled = false;
                    elements.buildModelBtn.textContent = '生成模型';
                }
            } else if (result.state === 'FAILURE') {
                console.log('模型构建任务失败'); // 添加调试日志
                clearInterval(pollingInterval);
                if (elements.buildModelStatus) {
                    updateStatus(elements.buildModelStatus, '❌ 模型构建失败: ' + result.error, true);
                }
                isBuildingModel = false;
                if (elements.buildModelBtn) {
                    elements.buildModelBtn.disabled = false;
                    elements.buildModelBtn.textContent = '生成模型';
                }
            } else {
                // 任务仍在进行中
                console.log('模型构建任务仍在进行中:', result.status); // 添加调试日志
                if (elements.buildModelStatus) {
                    const message = result.status || '模型构建任务进行中...';
                    updateStatus(elements.buildModelStatus, `<span class="loading"></span>${message}`);
                }
            }
        } catch (error) {
            console.error('轮询模型构建任务状态失败:', error);
            clearInterval(pollingInterval);
            if (elements.buildModelStatus) {
                updateStatus(elements.buildModelStatus, '❌ 轮询模型构建任务状态失败: ' + error.message, true);
            }
            isBuildingModel = false;
            if (elements.buildModelBtn) {
                elements.buildModelBtn.disabled = false;
                elements.buildModelBtn.textContent = '生成模型';
            }
        }
    }, POLLING_INTERVAL);
}

// 上传文件并构建模型
async function uploadAndBuildModel() {
    if (isUploadingModel) {
        alert('模型构建已在进行中，请稍候...');
        return;
    }

    const fileInput = elements.modelFile;
    const platformSelect = elements.platformType;

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        alert('请选择要上传的JSON文件');
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.endsWith('.json')) {
        alert('只支持上传JSON文件');
        return;
    }

    isUploadingModel = true;

    if (elements.uploadModelBtn) {
        elements.uploadModelBtn.disabled = true;
        elements.uploadModelBtn.textContent = '上传并构建中...';
    }

    if (elements.uploadModelStatus) {
        updateStatus(elements.uploadModelStatus, '<span class="loading"></span>正在上传文件并提交模型构建任务...');
    }

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('platform', platformSelect.value);

        const response = await fetch('/api/upload-and-build-model', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            if (elements.uploadModelStatus) {
                updateStatus(elements.uploadModelStatus, '<span class="loading"></span>模型构建任务已提交，正在处理中...');
            }

            // 启动模型构建任务状态轮询
            startBuildModelPollingForUpload(result.task_id, platformSelect.value);
        } else {
            throw new Error(result.message || '提交模型构建任务失败');
        }
    } catch (error) {
        if (elements.uploadModelStatus) {
            updateStatus(elements.uploadModelStatus, '❌ 提交模型构建任务出错: ' + error.message, true);
        }
        isUploadingModel = false;
        if (elements.uploadModelBtn) {
            elements.uploadModelBtn.disabled = false;
            elements.uploadModelBtn.textContent = '上传并构建模型';
        }
    }
}

// 为上传文件的模型构建任务启动状态轮询
async function startBuildModelPollingForUpload(taskId, platform) {
    console.log('开始轮询上传文件的模型构建任务状态，任务ID:', taskId); // 添加调试日志
    const pollingInterval = setInterval(async () => {
        try {
            const result = await ApiClient.getBuildModelStatus(taskId);
            console.log('上传文件的模型构建任务状态轮询结果:', result); // 添加调试日志

            if (result.state === 'SUCCESS') {
                console.log('上传文件的模型构建任务成功完成'); // 添加调试日志
                clearInterval(pollingInterval);
                if (elements.uploadModelStatus) {
                    updateStatus(elements.uploadModelStatus, '✅ ' + result.result.message);
                }

                // 显示结果区域
                if (elements.resultSection) {
                    showElement(elements.resultSection);
                }

                // 保存当前平台信息供后续使用
                currentTaskType = platform + '-model'; // 设置一个虚拟的任务类型用于平台识别

                isUploadingModel = false;
                if (elements.uploadModelBtn) {
                    elements.uploadModelBtn.disabled = false;
                    elements.uploadModelBtn.textContent = '重新上传并构建模型';
                }
            } else if (result.state === 'FAILURE') {
                console.log('上传文件的模型构建任务失败'); // 添加调试日志
                clearInterval(pollingInterval);
                if (elements.uploadModelStatus) {
                    updateStatus(elements.uploadModelStatus, '❌ 模型构建失败: ' + result.error, true);
                }
                isUploadingModel = false;
                if (elements.uploadModelBtn) {
                    elements.uploadModelBtn.disabled = false;
                    elements.uploadModelBtn.textContent = '上传并构建模型';
                }
            } else {
                // 任务仍在进行中
                console.log('上传文件的模型构建任务仍在进行中:', result.status); // 添加调试日志
                if (elements.uploadModelStatus) {
                    const message = result.status || '模型构建任务进行中...';
                    updateStatus(elements.uploadModelStatus, `<span class="loading"></span>${message}`);
                }
            }
        } catch (error) {
            console.error('轮询上传文件的模型构建任务状态失败:', error);
            clearInterval(pollingInterval);
            if (elements.uploadModelStatus) {
                updateStatus(elements.uploadModelStatus, '❌ 轮询模型构建任务状态失败: ' + error.message, true);
            }
            isUploadingModel = false;
            if (elements.uploadModelBtn) {
                elements.uploadModelBtn.disabled = false;
                elements.uploadModelBtn.textContent = '上传并构建模型';
            }
        }
    }, POLLING_INTERVAL);
}

// 切换问答区域显示
function toggleQASection() {
    if (elements.qaSection) {
        elements.qaSection.classList.toggle('hidden');
    }
}



// 提问
async function askQuestion() {
    if (isAsking) {
        alert('提问已在处理中，请稍候...');
        return;
    }

    const question = elements.qaInput ? elements.qaInput.value.trim() : '';
    if (!question) {
        alert('请输入问题');
        return;
    }

    isAsking = true;
    if (elements.qaSubmit) {
        elements.qaSubmit.disabled = true;
        elements.qaSubmit.textContent = '提问中...';
    }

    try {
        // 获取当前平台类型
        let platform = getCurrentPlatform(currentTaskType);

        // 如果是通过上传文件构建的模型，需要从其他方式获取平台类型
        if (!platform || platform === 'undefined') {
            // 尝试从平台选择下拉框获取
            const platformSelect = document.getElementById('platform-type');
            if (platformSelect && platformSelect.value) {
                platform = platformSelect.value;
            } else {
                // 默认使用zhihu平台
                platform = 'zhihu';
            }
        }

        const modelName = platform + '_model';
        console.log('提交问答任务，问题:', question, '平台:', platform, '模型名:', modelName); // 添加调试日志

        const result = await ApiClient.askQuestion(question, modelName);
        console.log('提交问答任务返回结果:', result); // 添加调试日志

        if (result.success) {
            // 显示加载状态
            const qaItem = document.createElement('div');
            qaItem.className = 'qa-item';
            qaItem.innerHTML = `
                <div class="question">
                    <strong>问:</strong> ${question}
                </div>
                <div class="answer">
                    <strong>答:</strong> <span class="loading">正在处理中...</span>
                </div>
            `;
            elements.qaHistory.insertBefore(qaItem, elements.qaHistory.firstChild);
            showElement(elements.qaHistory);

            // 清空输入框
            if (elements.qaInput) {
                elements.qaInput.value = '';
            }

            // 启动问答任务状态轮询
            startAskPolling(result.task_id, qaItem);
        } else {
            throw new Error(result.message || '提交问答任务失败');
        }
    } catch (error) {
        alert('提交问答任务出错: ' + error.message);
        isAsking = false;
        if (elements.qaSubmit) {
            elements.qaSubmit.disabled = false;
            elements.qaSubmit.textContent = '提问';
        }
    }
}


// 启动问答任务状态轮询
async function startAskPolling(taskId, qaItem) {
    const answerElement = qaItem.querySelector('.answer');
    const pollingInterval = setInterval(async () => {
        try {
            const result = await ApiClient.getAskStatus(taskId);
            console.log('问答任务状态轮询结果:', result); // 添加调试日志

            if (result.state === 'SUCCESS') {
                console.log('问答任务成功完成'); // 添加调试日志
                clearInterval(pollingInterval);
                answerElement.innerHTML = `<strong>答:</strong> ${result.result.answer}`;
                isAsking = false;
                if (elements.qaSubmit) {
                    elements.qaSubmit.disabled = false;
                    elements.qaSubmit.textContent = '提问';
                }
            } else if (result.state === 'FAILURE') {
                console.log('问答任务失败'); // 添加调试日志
                clearInterval(pollingInterval);
                answerElement.innerHTML = `<strong>答:</strong> <span class="error">问答任务失败: ${result.error}</span>`;
                isAsking = false;
                if (elements.qaSubmit) {
                    elements.qaSubmit.disabled = false;
                    elements.qaSubmit.textContent = '提问';
                }
            } else {
                // 任务仍在进行中
                console.log('问答任务仍在进行中:', result.status); // 添加调试日志
                answerElement.innerHTML = `<strong>答:</strong> <span class="loading">正在处理中...</span>`;
            }
        } catch (error) {
            console.error('轮询问答任务状态失败:', error);
            clearInterval(pollingInterval);
            answerElement.innerHTML = `<strong>答:</strong> <span class="error">轮询问答任务状态失败: ${error.message}</span>`;
            isAsking = false;
            if (elements.qaSubmit) {
                elements.qaSubmit.disabled = false;
                elements.qaSubmit.textContent = '提问';
            }
        }
    }, POLLING_INTERVAL);
}


// 下载结果
async function downloadResult() {
    if (!currentTaskId) {
        alert('没有可下载的任务');
        return;
    }

    try {
        await ApiClient.downloadResult(currentTaskId);
    } catch (error) {
        alert('下载失败: ' + error.message);
    }
}

// 总结内容
async function summarizeContent() {
    if (isSummarizing) {
        alert('总结内容已在运行中，请稍候...');
        return;
    }

    if (!elements.summaryResult) {
        alert('页面元素错误，请刷新页面重试');
        return;
    }

    isSummarizing = true;
    if (elements.summarizeBtn) {
        elements.summarizeBtn.disabled = true;
        elements.summarizeBtn.textContent = '总结中...';
    }

    // 显示加载状态
    elements.summaryResult.innerHTML = '<div class="loading">正在提交总结任务...</div>';
    showElement(elements.summaryResult);

    try {
        // 获取当前平台类型
        let platform = getCurrentPlatform(currentTaskType);

        // 如果是通过上传文件构建的模型，需要从其他方式获取平台类型
        if (!platform || platform === 'undefined') {
            // 尝试从平台选择下拉框获取
            const platformSelect = document.getElementById('platform-type');
            if (platformSelect && platformSelect.value) {
                platform = platformSelect.value;
            } else {
                // 默认使用zhihu平台
                platform = 'zhihu';
            }
        }

        const modelName = platform + '_model';
        console.log('提交总结任务，平台:', platform, '模型名:', modelName); // 添加调试日志

        const result = await ApiClient.getContentSummary(modelName);

        if (result.success) {
            elements.summaryResult.innerHTML = '<div class="loading">总结任务已提交，正在处理中...</div>';

            // 启动总结任务状态轮询
            startSummarizePolling(result.task_id);
        } else {
            throw new Error(result.message || '提交总结任务失败');
        }
    } catch (error) {
        elements.summaryResult.innerHTML = `<div class="error">❌ 提交总结任务出错: ${error.message}</div>`;
        isSummarizing = false;
        if (elements.summarizeBtn) {
            elements.summarizeBtn.disabled = false;
            elements.summarizeBtn.textContent = '总结内容';
        }
    }
}

// 启动总结任务状态轮询
async function startSummarizePolling(taskId) {
    const pollingInterval = setInterval(async () => {
        try {
            const result = await ApiClient.getSummarizeStatus(taskId);
            console.log('总结任务状态轮询结果:', result); // 添加调试日志

            if (result.state === 'SUCCESS') {
                console.log('总结任务成功完成'); // 添加调试日志
                clearInterval(pollingInterval);
                // 确保正确显示总结内容
                console.log('elements.summaryResult:', elements.summaryResult); // 调试日志
                if (elements.summaryResult) {
                    // 检查result.result.summary是否存在
                    console.log('总结内容:', result.result.summary); // 调试日志
                    if (result.result && result.result.summary) {
                        // 确保元素可见
                        elements.summaryResult.classList.remove('hidden');
                        elements.summaryResult.innerHTML = `
                            <div class="summary-content">
                                <h3>内容总结</h3>
                                <div class="summary-text">${result.result.summary.replace(/\n/g, '<br>')}</div>
                            </div>
                        `;
                        console.log('总结内容已更新到页面');
                    } else {
                        elements.summaryResult.innerHTML = `
                            <div class="summary-content">
                                <h3>内容总结</h3>
                                <div class="summary-text">未生成有效总结内容</div>
                            </div>
                        `;
                    }
                } else {
                    console.error('summaryResult元素未找到');
                }
                isSummarizing = false;
                if (elements.summarizeBtn) {
                    elements.summarizeBtn.disabled = false;
                    elements.summarizeBtn.textContent = '总结内容';
                }
            } else if (result.state === 'FAILURE') {
                console.log('总结任务失败'); // 添加调试日志
                clearInterval(pollingInterval);
                if (elements.summaryResult) {
                    elements.summaryResult.innerHTML = `<div class="error">❌ 总结任务失败: ${result.error}</div>`;
                }
                isSummarizing = false;
                if (elements.summarizeBtn) {
                    elements.summarizeBtn.disabled = false;
                    elements.summarizeBtn.textContent = '总结内容';
                }
            } else {
                // 任务仍在进行中
                console.log('总结任务仍在进行中:', result.status); // 添加调试日志
                if (elements.summaryResult) {
                    elements.summaryResult.innerHTML = '<div class="loading">总结任务进行中...</div>';
                }
            }
        } catch (error) {
            console.error('轮询总结任务状态失败:', error);
            clearInterval(pollingInterval);
            if (elements.summaryResult) {
                elements.summaryResult.innerHTML = `<div class="error">❌ 轮询总结任务状态失败: ${error.message}</div>`;
            }
            isSummarizing = false;
            if (elements.summarizeBtn) {
                elements.summarizeBtn.disabled = false;
                elements.summarizeBtn.textContent = '总结内容';
            }
        }
    }, POLLING_INTERVAL);
}
