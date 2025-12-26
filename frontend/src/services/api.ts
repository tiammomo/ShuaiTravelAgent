import axios from 'axios';
import {
  SessionInfo,
  ChatRequest,
  ChatResponse,
  AvailableModelsResponse,
  SetModelRequest,
  SetModelResponse,
  GetSessionModelResponse
} from '../types';

const API_BASE = '/api';

// API服务类
class APIService {
  // 健康检查
  async checkHealth(): Promise<{ status: string; agent: string; version: string }> {
    const response = await axios.get(`${API_BASE}/health`);
    return response.data;
  }

  // 创建新会话
  async createSession(): Promise<{ session_id: string }> {
    const response = await axios.post(`${API_BASE}/session/new`);
    return response.data;
  }

  // 获取会话列表
  async getSessions(): Promise<{ sessions: SessionInfo[] }> {
    const response = await axios.get(`${API_BASE}/sessions`);
    return response.data;
  }

  // 删除会话
  async deleteSession(sessionId: string): Promise<{ success: boolean }> {
    const response = await axios.delete(`${API_BASE}/session/${sessionId}`);
    return response.data;
  }

  // 清空对话
  async clearChat(sessionId: string): Promise<ChatResponse> {
    const response = await axios.post(`${API_BASE}/clear`, null, {
      params: { session_id: sessionId }
    });
    return response.data;
  }

  // 更新会话名称
  async updateSessionName(sessionId: string, name: string): Promise<{ success: boolean; message: string }> {
    const response = await axios.put(`${API_BASE}/session/${sessionId}/name`, { name });
    return response.data;
  }

  // 发送普通聊天消息
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await axios.post(`${API_BASE}/chat`, request);
    return response.data;
  }

  // 获取可用模型列表
  async getAvailableModels(): Promise<AvailableModelsResponse> {
    const response = await axios.get(`${API_BASE}/models`);
    return response.data;
  }

  // 设置会话模型
  async setSessionModel(sessionId: string, modelId: string): Promise<SetModelResponse> {
    const response = await axios.put(
      `${API_BASE}/session/${sessionId}/model`,
      { model_id: modelId } as SetModelRequest
    );
    return response.data;
  }

  // 获取会话当前模型
  async getSessionModel(sessionId: string): Promise<GetSessionModelResponse> {
    const response = await axios.get(`${API_BASE}/session/${sessionId}/model`);
    return response.data;
  }

  // SSE流式聊天（通过EventSource处理）
  createChatStream(request: ChatRequest, callbacks: {
    onChunk: (content: string) => void;
    onError: (error: string) => void;
    onComplete: () => void;
  }): EventSource {
    const url = new URL(`${window.location.origin}${API_BASE}/chat/stream`);

    // 使用POST请求的Body数据需要特殊处理
    // EventSource只支持GET，所以需要通过服务端配置或使用fetch
    // 这里我们使用fetch + ReadableStream替代EventSource

    this.fetchStreamChat(request, callbacks);

    // 返回一个空的EventSource（实际使用fetch）
    return new EventSource('');
  }

  // 使用fetch处理SSE流
  async fetchStreamChat(request: ChatRequest, callbacks: {
    onChunk: (content: string) => void;
    onError: (error: string) => void;
    onComplete: () => void;
    onStop?: () => boolean;
  }): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        callbacks.onError(`HTTP error! status: ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        callbacks.onError('无法读取响应流');
        return;
      }

      while (true) {
        // 检查是否需要停止
        if (callbacks.onStop && callbacks.onStop()) {
          reader.cancel();
          break;
        }

        const { done, value } = await reader.read();

        if (done) {
          callbacks.onComplete();
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();

            if (dataStr === '[DONE]') {
              callbacks.onComplete();
              return;
            }

            try {
              const data = JSON.parse(dataStr);

              if (data.chunk) {
                callbacks.onChunk(data.chunk);
              } else if (data.error) {
                callbacks.onError(data.error);
                return;
              }
            } catch (e) {
              // 忽略JSON解析错误
            }
          }
        }
      }
    } catch (error) {
      callbacks.onError(error instanceof Error ? error.message : '网络错误');
    }
  }
}

export const apiService = new APIService();
