// frontend/js/main.js
// 任务配置模板
const taskConfigs = {
    'zhihu-question': {
        'logintype': { label: '登录方式', type: 'select', options: ['cookie', 'qrcode'] },
        'question-url': { label: '问题链接', type: 'text', placeholder: '请输入知乎问题链接' },
        'crawlertype': { label: '爬取类型', type: 'hidden', value: 'question' },
        'platform': { label: '平台', type: 'hidden', value: 'zhihu' }
    },
    'bili-video': {
        'logintype': { label: '登录方式', type: 'select', options: ['cookie', 'qrcode'] },
        'video-url': { label: '视频链接', type: 'text', placeholder: '请输入B站视频链接' },
        'crawlertype': { label: '爬取类型', type: 'hidden', value: 'detail' },
        'platform': { label: '平台', type: 'hidden', value: 'bili' }
    },
    'xhs-detail': {
        'logintype': { label: '登录方式', type: 'select', options: ['cookie', 'qrcode'] },
        'post-url': { label: '帖子链接', type: 'text', placeholder: '请输入小红书帖子链接' },
        'crawlertype': { label: '爬取类型', type: 'hidden', value: 'detail' },
        'platform': { label: '平台', type: 'hidden', value: 'xhs' }
    }
};

// DOM元素
let taskTypeSelect, configSection, dynamicConfig, runBtn, runStatus, resultSection;
let summarizeBtn, summaryResult, qaSection, qaBtn, qaInput, qaSubmit, qaHistory;

// 当前选择的任务类型和任务ID
let currentTaskType = '';
let currentTaskId = '';

// 防止重复点击的标志
let isSummarizing = false;
let isAsking = false;

// 初始化应用
document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    attachEventListeners();
});

// 初始化DOM元素引用
function initializeElements() {
    taskTypeSelect = document.getElementById('task-type');
    configSection = document.getElementById('config-section');
    dynamicConfig = document.getElementById('dynamic-config');
    runBtn = document.getElementById('run-btn');
    runStatus = document.getElementById('run-status');
    resultSection = document.getElementById('result-section');
    summarizeBtn = document.getElementById('summarize-btn');
    summaryResult = document.getElementById('summary-result');
    qaSection = document.getElementById('qa-section');
    qaBtn = document.getElementById('qa-btn');
    qaInput = document.getElementById('qa-input');
    qaSubmit = document.getElementById('qa-submit');
    qaHistory = document.getElementById('qa-history');
}

// 绑定事件监听器
function attachEventListeners() {
    taskTypeSelect.addEventListener('change', handleTaskTypeChange);
    runBtn.addEventListener('click', runCrawler);
    summarizeBtn.addEventListener('click', summarizeContent);
    qaBtn.addEventListener('click', toggleQASection);
    qaSubmit.addEventListener('click', askQuestion);
    qaInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') askQuestion();
    });
}

// 处理任务类型变化
function handleTaskTypeChange() {
    currentTaskType = taskTypeSelect.value;

    if (currentTaskType && taskConfigs[currentTaskType]) {
        configSection.classList.remove('hidden');
        renderDynamicConfig();
        runBtn.disabled = false;
    } else {
        configSection.classList.add('hidden');
        runBtn.disabled = true;
    }
}

// 渲染动态配置表单
function renderDynamicConfig() {
    dynamicConfig.innerHTML = '';
    const config = taskConfigs[currentTaskType];

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
            } else if (field.type === 'text') {
                const input = document.createElement('input');
                input.type = 'text';
                input.id = key;
                input.placeholder = field.placeholder || '';
                formGroup.appendChild(input);
            }
        }

        dynamicConfig.appendChild(formGroup);
    }
}

// 运行爬虫
async function runCrawler() {
    // 生成唯一的任务ID
    currentTaskId = 'task_' + Date.now();

    // 收集配置参数
    const config = {
        task_id: currentTaskId,
        'task-type': currentTaskType  // 添加task-type参数
    };
    const configElements = dynamicConfig.querySelectorAll('input, select');
    configElements.forEach(el => {
        if (el.type !== 'hidden' || el.id) {
            config[el.id] = el.value;
        }
    });

    // 禁用运行按钮，防止重复点击
    runBtn.disabled = true;
    runBtn.textContent = '运行中...';

    // 显示运行状态
    runStatus.classList.remove('hidden');
    runStatus.classList.remove('status-error');
    runStatus.classList.add('status-info');
    runStatus.innerHTML = '<span class="loading"></span>正在运行爬虫和生成模型，请稍候...';

    try {
        // 调用API运行爬虫
        const result = await ApiClient.runCrawler(config);

        if (result.success) {
            runStatus.innerHTML = '✅ ' + result.message;
            // 轮询任务状态直到完成
            await pollTaskStatus(currentTaskId);
        } else {
            throw new Error(result.message || '运行失败');
        }
    } catch (error) {
        runStatus.classList.remove('status-info');
        runStatus.classList.add('status-error');
        runStatus.innerHTML = '❌ 运行出错: ' + error.message;
        // 重新启用按钮
        runBtn.disabled = false;
        runBtn.textContent = '运行爬虫和生成模型';
    }
}

// 轮询任务状态
async function pollTaskStatus(taskId) {
    const pollInterval = 2000; // 2秒轮询一次

    const poll = async () => {
        try {
            const status = await ApiClient.getTaskStatus(taskId);

            if (status.status === 'running') {
                // 任务仍在运行，继续轮询
                setTimeout(poll, pollInterval);
            } else if (status.status === 'completed') {
                // 任务完成
                runStatus.innerHTML = '✅ ' + status.message;
                resultSection.classList.remove('hidden');
                // 重新启用按钮
                runBtn.disabled = false;
                runBtn.textContent = '运行爬虫和生成模型';
            } else if (status.status === 'error') {
                // 任务出错
                runStatus.classList.remove('status-info');
                runStatus.classList.add('status-error');
                runStatus.innerHTML = '❌ ' + status.message;
                // 重新启用按钮
                runBtn.disabled = false;
                runBtn.textContent = '运行爬虫和生成模型';
            }
        } catch (error) {
            console.error('轮询任务状态出错:', error);
            // 重新启用按钮
            runBtn.disabled = false;
            runBtn.textContent = '运行爬虫和生成模型';
        }
    };

    // 开始轮询
    setTimeout(poll, pollInterval);
}

// 获取当前配置的平台类型
function getCurrentPlatform() {
    // 从隐藏的platform字段获取值
    const platformElement = document.getElementById('platform');
    if (platformElement) {
        return platformElement.value;
    }
}

// 总结内容
async function summarizeContent() {
    console.log('开始执行总结内容函数'); // 调试信息

    // 防止重复点击
    if (isSummarizing) {
        console.log('总结已在进行中'); // 调试信息
        alert('总结内容已在运行中，请稍候...');
        return;
    }

    // 检查必要的DOM元素是否存在
    if (!summaryResult) {
        console.error('summaryResult元素未找到'); // 错误信息
        alert('页面元素错误，请刷新页面重试');
        return;
    }

    // 设置标志位
    isSummarizing = true;
    // 禁用按钮
    if (summarizeBtn) {
        summarizeBtn.disabled = true;
        summarizeBtn.textContent = '总结中...';
    }

    // 显示加载状态
    console.log('显示加载状态'); // 调试信息
    summaryResult.classList.remove('hidden');
    summaryResult.innerHTML = '<div class="loading-content"><span class="loading"></span>正在生成内容总结...</div>';

    // 确保元素可见
    console.log('summaryResult样式:', summaryResult.style); // 调试信息
    console.log('summaryResult类名:', summaryResult.className); // 调试信息

    try {
        // 获取平台类型以确定模型名称
        const platform = getCurrentPlatform();
        // const modelName = platform + '_model';
        const modelName = platform;

        console.log('请求总结内容，模型名:', modelName); // 调试信息

        const result = await ApiClient.getContentSummary(modelName);

        console.log('收到总结响应:', result); // 调试信息

        if (result.success) {
            // 构造要显示的内容
            const content = `<div class="summary-content">${result.summary}</div>`;
            console.log('准备显示的内容:', content); // 调试信息

            // 设置innerHTML并确保元素可见
            summaryResult.innerHTML = content;
            summaryResult.classList.remove('hidden');

            // 强制刷新元素显示
            summaryResult.style.display = 'block';
            console.log('内容已设置到页面'); // 调试信息
        } else {
            throw new Error('获取总结失败: ' + result.message);
        }
    } catch (error) {
        console.error('总结内容出错:', error); // 调试信息
        const errorContent = `<div class="error-content">❌ 获取总结出错: ${error.message}</div>`;
        summaryResult.innerHTML = errorContent;
        summaryResult.classList.remove('hidden');
        summaryResult.style.display = 'block';
    } finally {
        // 重置标志位和按钮状态
        isSummarizing = false;
        if (summarizeBtn) {
            summarizeBtn.disabled = false;
            summarizeBtn.textContent = '总结内容';
        }
        console.log('总结内容函数执行完毕'); // 调试信息
    }
}

// 切换问答区域显示
function toggleQASection() {
    qaSection.classList.toggle('hidden');
    if (!qaSection.classList.contains('hidden')) {
        qaInput.focus();
    }
}

// 提问
async function askQuestion() {
    const question = qaInput.value.trim();
    if (!question) return;

    // 防止重复点击
    if (isAsking) {
        alert('提问已在处理中，请稍候...');
        return;
    }

    // 设置标志位
    isAsking = true;

    // 禁用输入和按钮
    qaInput.disabled = true;
    qaSubmit.disabled = true;
    qaSubmit.textContent = '提问中...';

    // 添加问题到历史记录
    const qaItem = document.createElement('div');
    qaItem.className = 'qa-item';
    qaItem.innerHTML = `
        <div class="qa-question">问: ${question}</div>
        <div class="qa-answer"><span class="loading"></span>AI正在思考中...</div>
    `;
    qaHistory.prepend(qaItem);

    // 清空输入框
    qaInput.value = '';

    // 滚动到顶部
    qaHistory.scrollTop = 0;

    try {
        // 获取平台类型以确定模型名称
        const platform = getCurrentPlatform();
        const modelName = platform + '_model';

        const result = await ApiClient.askQuestion(question, modelName);

        if (result.success) {
            const answerElement = qaItem.querySelector('.qa-answer');
            // 使用innerHTML渲染回答内容
            answerElement.innerHTML = `答: ${result.answer}`;
        } else {
            throw new Error('获取回答失败: ' + result.message);
        }
    } catch (error) {
        const answerElement = qaItem.querySelector('.qa-answer');
        answerElement.innerHTML = `❌ 获取回答出错: ${error.message}`;
    } finally {
        // 重新启用输入和按钮
        qaInput.disabled = false;
        qaSubmit.disabled = false;
        qaSubmit.textContent = '提问';
        qaInput.focus();

        // 重置标志位
        isAsking = false;
    }
}
