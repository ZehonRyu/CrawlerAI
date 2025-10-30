// frontend/js/modules/config.js
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

function getTaskConfig(taskType) {
    return taskConfigs[taskType] || null;
}

export { taskConfigs, getTaskConfig };
