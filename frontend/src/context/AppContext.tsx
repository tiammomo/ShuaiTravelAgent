import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Message, AppConfig, ModelInfo } from '../types';
import { apiService } from '../services/api';

interface AppState {
  // 配置
  config: AppConfig;
  setConfig: (config: AppConfig) => void;

  // 模型管理
  availableModels: ModelInfo[];
  currentModelId: string | null;
  setCurrentModelId: (modelId: string) => void;
  loadingModels: boolean;

  // 会话
  currentSessionId: string | null;
  setCurrentSessionId: (id: string | null) => void;
  switchSession: (id: string | null) => void;  // 切换会话，保留消息

  // 消息
  messages: Message[];
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  setMessages: (messages: Message[]) => void;

  // 流式控制
  isStreaming: boolean;
  setIsStreaming: (streaming: boolean) => void;
  stopStreaming: boolean;
  setStopStreaming: (stop: boolean) => void;
}

const AppContext = createContext<AppState | undefined>(undefined);

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<AppConfig>({
    apiBase: 'http://localhost:8000'
  });

  // 模型相关状态
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [currentModelId, setCurrentModelIdState] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(true);

  const [currentSessionId, setCurrentSessionIdState] = useState<string | null>(null);
  const [messages, setMessagesState] = useState<Message[]>([]);
  // 会话消息缓存：保存每个会话的消息列表
  const [sessionMessages, setSessionMessages] = useState<Record<string, Message[]>>({});
  // 会话模型缓存：保存每个会话使用的模型ID
  const [sessionModelIds, setSessionModelIds] = useState<Record<string, string>>({});

  const [isStreaming, setIsStreaming] = useState(false);
  const [stopStreaming, setStopStreaming] = useState(false);

  // 加载可用模型列表
  useEffect(() => {
    const loadModels = async () => {
      try {
        setLoadingModels(true);
        const data = await apiService.getAvailableModels();
        if (data.success && data.models.length > 0) {
          setAvailableModels(data.models);
          // 设置默认模型
          setCurrentModelIdState(data.models[0].model_id);
        }
      } catch (error) {
        console.error('加载模型列表失败:', error);
        // 设置默认模型列表作为降级方案
        setAvailableModels([{
          model_id: 'gpt-4o-mini',
          name: 'OpenAI GPT-4o Mini',
          provider: 'openai',
          model: 'gpt-4o-mini'
        }]);
        setCurrentModelIdState('gpt-4o-mini');
      } finally {
        setLoadingModels(false);
      }
    };

    loadModels();
  }, []);

  // 设置当前模型
  const handleSetCurrentModelId = async (modelId: string) => {
    setCurrentModelIdState(modelId);

    // 如果有当前会话，同步设置会话模型
    if (currentSessionId) {
      try {
        await apiService.setSessionModel(currentSessionId, modelId);
        setSessionModelIds(prev => ({
          ...prev,
          [currentSessionId]: modelId
        }));
      } catch (error) {
        console.error('设置会话模型失败:', error);
      }
    }
  };
  
  const addMessage = (message: Message) => {
    setMessagesState(prev => {
      const newMessages = [...prev, message];
      // 同时更新缓存
      if (currentSessionId) {
        setSessionMessages(cache => ({
          ...cache,
          [currentSessionId]: newMessages
        }));
      }
      return newMessages;
    });
  };
  
  const clearMessages = () => {
    setMessagesState([]);
    // 清空当前会话的缓存
    if (currentSessionId) {
      setSessionMessages(cache => ({
        ...cache,
        [currentSessionId]: []
      }));
    }
  };
  
  const setMessages = (newMessages: Message[]) => {
    setMessagesState(newMessages);
    // 更新缓存
    if (currentSessionId) {
      setSessionMessages(cache => ({
        ...cache,
        [currentSessionId]: newMessages
      }));
    }
  };

  // 设置当前会话（不切换消息）
  const setCurrentSessionId = (id: string | null) => {
    setCurrentSessionIdState(id);
  };

  // 切换会话（保留消息）
  const switchSession = async (id: string | null) => {
    // 保存当前会话的消息
    if (currentSessionId && messages.length > 0) {
      setSessionMessages(cache => ({
        ...cache,
        [currentSessionId]: messages
      }));
    }

    // 切换到新会话
    setCurrentSessionIdState(id);

    // 加载新会话的消息（如果有缓存）
    if (id && sessionMessages[id]) {
      setMessagesState(sessionMessages[id]);
    } else {
      setMessagesState([]);
    }

    // 切换会话时，加载该会话的模型
    if (id) {
      try {
        const data = await apiService.getSessionModel(id);
        if (data.success && data.model_id && data.model_id !== 'default') {
          setCurrentModelIdState(data.model_id);
          setSessionModelIds(prev => ({
            ...prev,
            [id]: data.model_id
          }));
        } else {
          // 使用当前选择的模型
          if (currentModelId) {
            setSessionModelIds(prev => ({
              ...prev,
              [id]: currentModelId
            }));
          }
        }
      } catch (error) {
        console.error('获取会话模型失败:', error);
        // 使用当前选择的模型
        if (currentModelId) {
          setSessionModelIds(prev => ({
            ...prev,
            [id]: currentModelId
          }));
        }
      }
    }
  };
  
  const value: AppState = {
    config,
    setConfig,
    availableModels,
    currentModelId,
    setCurrentModelId: handleSetCurrentModelId,
    loadingModels,
    currentSessionId,
    setCurrentSessionId,
    switchSession,
    messages,
    addMessage,
    clearMessages,
    setMessages,
    isStreaming,
    setIsStreaming,
    stopStreaming,
    setStopStreaming,
  };
  
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useAppContext = (): AppState => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
};
