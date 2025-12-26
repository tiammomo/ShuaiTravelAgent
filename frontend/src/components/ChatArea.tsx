import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Space } from 'antd';
import { SendOutlined, StopOutlined } from '@ant-design/icons';
import { useAppContext } from '../context/AppContext';
import { apiService } from '../services/api';
import MessageList from './MessageList';

const { TextArea } = Input;

// 自定义 Hook：动态加载动画
const useLoadingDots = (isLoading: boolean) => {
  const [dots, setDots] = useState('');

  useEffect(() => {
    if (!isLoading) {
      setDots('');
      return;
    }

    const interval = setInterval(() => {
      setDots((prev) => {
        if (prev === '') return '.';
        if (prev === '.') return '..';
        if (prev === '..') return '...';
        return '';
      });
    }, 500);

    return () => clearInterval(interval);
  }, [isLoading]);

  return dots;
};

const ChatArea: React.FC = () => {
  const {
    currentSessionId,
    setCurrentSessionId,
    messages,
    addMessage,
    isStreaming,
    setIsStreaming,
    stopStreaming,
    setStopStreaming,
  } = useAppContext();

  const [inputValue, setInputValue] = useState('');
  const [streamingMessage, setStreamingMessage] = useState('');
  const [waitingForResponse, setWaitingForResponse] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 使用动态加载动画
  const loadingDots = useLoadingDots(waitingForResponse);

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  // 发送消息
  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMessageContent = inputValue.trim();
    
    // 检查是否是首次发送消息（无会话或当前会话无消息）
    const isFirstMessage = !currentSessionId || messages.length === 0;

    // 如果没有会话，自动创建
    let sessionId = currentSessionId;
    if (!sessionId) {
      try {
        const data = await apiService.createSession();
        sessionId = data.session_id;
        setCurrentSessionId(sessionId);
      } catch (error) {
        console.error('创建会话失败:', error);
        return;
      }
    }

    const userMessage = {
      role: 'user' as const,
      content: inputValue,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    };

    // 立即添加用户消息
    addMessage(userMessage);
    setInputValue('');
    setIsStreaming(true);
    setStopStreaming(false);
    setWaitingForResponse(true);
    setIsThinking(true);

    // 如果是首次发送消息，设置会话名称
    if (isFirstMessage) {
      try {
        const sessionName = userMessageContent.slice(0, 15) + (userMessageContent.length > 15 ? '...' : '');
        await apiService.updateSessionName(sessionId, sessionName);
      } catch (error) {
        console.error('设置会话名称失败:', error);
      }
    }

    // 初始化流式消息
    let fullResponse = '';
    let firstChunk = true;

    // 发起流式请求
    await apiService.fetchStreamChat(
      {
        message: userMessage.content,
        session_id: sessionId,
      },
      {
        onChunk: (content) => {
          if (firstChunk) {
            setWaitingForResponse(false);
            setIsThinking(false);
            firstChunk = false;
          }
          fullResponse += content;
          setStreamingMessage((prev) => {
            if (!prev) return content;
            return prev + content;
          });
        },
        onError: (error) => {
          setWaitingForResponse(false);
          setIsThinking(false);
          const errorMsg = `抱歉，出现错误：${error}`;
          setStreamingMessage(errorMsg);
          fullResponse = errorMsg;
        },
        onComplete: () => {
          setWaitingForResponse(false);
          setIsThinking(false);
          const finalMessage = {
            role: 'assistant' as const,
            content: fullResponse || streamingMessage,
            timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
          };
          addMessage(finalMessage);
          setStreamingMessage('');
          setIsStreaming(false);
        },
        onStop: () => stopStreaming,
      }
    );

    // 如果被停止
    if (stopStreaming) {
      setWaitingForResponse(false);
      setIsThinking(false);
      const finalMessage = {
        role: 'assistant' as const,
        content: fullResponse + '\n\n⚠️ 已停止生成',
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      };
      addMessage(finalMessage);
      setStreamingMessage('');
      setIsStreaming(false);
      setStopStreaming(false);
    }
  };

  // 停止生成
  const handleStop = () => {
    setStopStreaming(true);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ margin: 0 }}>小帅旅游助手</h2>
        <p style={{ margin: '4px 0 0 0', color: '#666' }}>为您提供个性化的旅游推荐和路线规划</p>
      </div>

      <div style={{ flex: 1, overflow: 'auto', marginBottom: '16px' }}>
        <MessageList messages={messages} streamingMessage={streamingMessage} loadingDots={loadingDots} isThinking={isThinking} />
        <div ref={messagesEndRef} />
      </div>

      <div>
        {!currentSessionId && messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '16px', background: '#e6f7ff', borderRadius: '8px', marginBottom: '16px' }}>
            💬 发送消息开始对话
          </div>
        )}
        
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={isStreaming ? "正在生成回答中..." : "输入你的旅游需求..."}
            disabled={isStreaming}
            autoSize={{ minRows: 1, maxRows: 4 }}
            style={{ resize: 'none' }}
          />
          {isStreaming ? (
            <Button
              type="primary"
              danger
              icon={<StopOutlined />}
              onClick={handleStop}
            >
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!inputValue.trim()}
            >
              发送
            </Button>
          )}
        </Space.Compact>
      </div>
    </div>
  );
};

export default ChatArea;
