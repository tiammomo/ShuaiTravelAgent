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
    refreshSessions,
  } = useAppContext();

  const [inputValue, setInputValue] = useState('');
  const [streamingMessage, setStreamingMessage] = useState('');
  const [streamingReasoning, setStreamingReasoning] = useState('');
  const [waitingForResponse, setWaitingForResponse] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [isAnswering, setIsAnswering] = useState(false);
  const [reasoningContent, setReasoningContent] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 使用动态加载动画
  const loadingDots = useLoadingDots(waitingForResponse);

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage, streamingReasoning]);

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
    setIsAnswering(false);

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
    let fullReasoning = '';

    // 重置状态
    setStreamingMessage('');
    setStreamingReasoning('');
    setReasoningContent('');

    // 发起流式请求
    await apiService.fetchStreamChat(
      {
        message: userMessage.content,
        session_id: sessionId,
      },
      {
        // 处理回答内容
        onChunk: (content) => {
          // 离开思考阶段，进入回答阶段
          if (isThinking || isAnswering === false) {
            setIsThinking(false);
            setIsAnswering(true);
          }
          fullResponse += content;
          setStreamingMessage((prev) => prev + content);
        },
        // 处理思考过程内容
        onReasoning: (content) => {
          fullReasoning += content;
          setStreamingReasoning((prev) => prev + content);
        },
        // 思考过程开始
        onReasoningStart: () => {
          setIsThinking(true);
          setIsAnswering(false);
        },
        // 思考过程结束
        onReasoningEnd: () => {
          setReasoningContent(fullReasoning);
        },
        // 回答开始
        onAnswerStart: () => {
          setIsAnswering(true);
          setIsThinking(false);
        },
        // 元数据
        onMetadata: () => {
          // 元数据处理（可扩展）
        },
        // 错误处理
        onError: (error) => {
          setWaitingForResponse(false);
          setIsThinking(false);
          setIsAnswering(false);
          const errorMsg = `抱歉，出现错误：${error}`;
          setStreamingMessage(errorMsg);
          fullResponse = errorMsg;
        },
        // 完成
        onComplete: () => {
          setWaitingForResponse(false);
          setIsThinking(false);
          setIsAnswering(false);

          // 合并思考过程和回答内容
          const finalMessage = {
            role: 'assistant' as const,
            content: fullResponse || streamingMessage,
            reasoning: fullReasoning || reasoningContent || streamingReasoning,
            timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
          };
          addMessage(finalMessage);
          setStreamingMessage('');
          setStreamingReasoning('');
          setIsStreaming(false);
          // 自动刷新会话列表
          refreshSessions();
        },
        onStop: () => stopStreaming,
      }
    );

    // 如果被停止
    if (stopStreaming) {
      setWaitingForResponse(false);
      setIsThinking(false);
      setIsAnswering(false);
      const finalMessage = {
        role: 'assistant' as const,
        content: fullResponse + '\n\n⚠️ 已停止生成',
        reasoning: fullReasoning || reasoningContent,
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      };
      addMessage(finalMessage);
      setStreamingMessage('');
      setStreamingReasoning('');
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
        {/* 显示思考过程流 */}
        {isThinking && streamingReasoning && (
          <MessageList
            messages={[]}
            streamingMessage=""
            isThinking={true}
            thinkingContent={streamingReasoning}
          />
        )}
        {/* 显示回答流 */}
        <MessageList
          messages={messages}
          streamingMessage={streamingMessage}
          loadingDots={loadingDots}
          isThinking={isThinking && !streamingReasoning}
        />
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
