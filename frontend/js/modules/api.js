// frontend/js/modules/api.js
class ApiClient {
    static BASE_URL = '/api';

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

static async getContentSummary(modelName = 'zhihu_model') {
    try {
        console.log('提交总结任务，模型名:', modelName); // 添加调试日志
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

static async askQuestion(question, modelName) {
    try {
        console.log('提交问答任务，问题:', question, '模型名:', modelName); // 添加调试日志
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

    static async getSummarizeStatus(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/summarize-status/${taskId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('获取总结状态响应:', data); // 添加调试日志
            return data;
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应');
        }
    }

    static async sendHeartbeat(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/task-heartbeat/${taskId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('发送心跳失败:', error);
            throw new Error('发送心跳失败');
        }
    }

    static async cancelTask(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/cancel-task/${taskId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('取消任务失败:', error);
            throw new Error('取消任务失败');
        }
    }

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

    static async getAskStatus(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/ask-status/${taskId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应');
        }
    }

    static async getQrCode(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/qrcode/${taskId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应');
        }
    }

    static async downloadResult(taskId) {
        try {
            // 直接发起下载请求
            const response = await fetch(`${this.BASE_URL}/download/${taskId}`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }

            // 获取文件名
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'result.json';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                if (filenameMatch && filenameMatch.length === 2) {
                    filename = filenameMatch[1];
                }
            }

            // 创建下载链接
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            return { success: true };
        } catch (error) {
            console.error('下载出错:', error);
            throw new Error('下载失败: ' + error.message);
        }
    }

    // 新增：生成模型的API调用
    static async buildModel(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/build-model/${taskId}`, {
                method: 'POST'
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

    // 新增：获取模型构建任务状态
    static async getBuildModelStatus(taskId) {
        try {
            const response = await fetch(`${this.BASE_URL}/build-model-status/${taskId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('获取模型构建状态响应:', data); // 添加调试日志
            return data;
        } catch (error) {
            console.error('API调用错误:', error);
            throw new Error('网络错误或服务器无响应');
        }
    }
}

export { ApiClient };
