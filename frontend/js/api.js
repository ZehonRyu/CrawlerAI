// frontend/js/api.js
// 这里应该包含与后端通信的API函数

class ApiClient {
    // 基础URL - 根据你的后端服务调整
    static BASE_URL = 'http://localhost:5000/api';

    // 运行爬虫
    static async runCrawler(config) {
        try {
            const response = await fetch(`${this.BASE_URL}/run-crawler`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应: ' + error.message);
        }
    }

    // 获取任务状态
    static async getTaskStatus(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/task-status/${taskId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应');
        }
    }

    // 获取内容总结
    static async getContentSummary(modelName = 'xhs_model') {
        try {
            const response = await fetch(`${this.BASE_URL}/summarize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ model_name: modelName })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应: ' + error.message);
        }
    }

    // 问答功能
    static async askQuestion(question, modelName) {
        try {
            const response = await fetch(`${this.BASE_URL}/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: question,
                    model_name: modelName
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应: ' + error.message);
        }
    }
}
