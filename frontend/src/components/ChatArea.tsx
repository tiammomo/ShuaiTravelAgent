import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Space, Card } from 'antd';
import { SendOutlined, StopOutlined, DownOutlined, UpOutlined } from '@ant-design/icons';
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
  const [error, setError] = useState<string | null>(null);
  // 思考过程展开状态（按会话ID存储）
  const [reasoningExpanded, setReasoningExpanded] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 使用动态加载动画
  const loadingDots = useLoadingDots(waitingForResponse);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage, streamingReasoning, isThinking, waitingForResponse]);

  // 监听会话变化，重置所有流式状态
  useEffect(() => {
    setStreamingMessage('');
    setStreamingReasoning('');
    setWaitingForResponse(false);
    setIsThinking(false);
    setError(null);
    setIsStreaming(false);
    setStopStreaming(false);
  }, [currentSessionId]);

  // 切换思考过程展开/折叠
  const toggleReasoning = (messageId: string) => {
    setReasoningExpanded(prev => ({
      ...prev,
      [messageId]: !prev[messageId]
    }));
  };

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
    setError(null);

    // 重置流式状态
    setStreamingMessage('');
    setStreamingReasoning('');

    // 如果是首次发送消息，设置会话名称
    if (isFirstMessage) {
      try {
        const sessionName = userMessageContent.slice(0, 15) + (userMessageContent.length > 15 ? '...' : '');
        await apiService.updateSessionName(sessionId, sessionName);
      } catch (error) {
        console.error('设置会话名称失败:', error);
      }
    }

    let fullResponse = '';
    let fullReasoning = '';

    // 发起流式请求
    await apiService.fetchStreamChat(
      {
        message: userMessage.content,
        session_id: sessionId,
      },
      {
        // 处理回答内容
        onChunk: (content) => {
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
        },
        // 思考过程结束
        onReasoningEnd: () => {
          setIsThinking(false);
        },
        // 回答开始
        onAnswerStart: () => {},
        // 元数据
        onMetadata: () => {},
        // 错误处理
        onError: (errorMsg) => {
          setWaitingForResponse(false);
          setIsThinking(false);
          setError(errorMsg);
          fullResponse = `抱歉，出现错误：${errorMsg}`;
        },
        // 完成
        onComplete: () => {
          const finalReasoning = fullReasoning;
          const finalContent = fullResponse || streamingMessage;

          // 创建最终消息（包含思考过程）
          const finalMessage = {
            role: 'assistant' as const,
            content: finalContent,
            reasoning: finalReasoning,
            timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
          };

          // 添加最终消息到历史
          addMessage(finalMessage);

          // 清空流式状态
          setStreamingMessage('');
          setStreamingReasoning('');
          setWaitingForResponse(false);
          setIsStreaming(false);
        },
        onStop: () => stopStreaming,
      }
    );

    // 刷新会话列表
    refreshSessions();
  };

  // 停止生成
  const handleStop = () => {
    setStopStreaming(true);
    setWaitingForResponse(false);
    setIsThinking(false);
    setIsStreaming(false);

    // 如果有部分内容，添加到消息历史
    if (streamingMessage || streamingReasoning) {
      const finalMessage = {
        role: 'assistant' as const,
        content: (streamingMessage || '已停止生成') + '\n\n⚠️ 已停止生成',
        reasoning: streamingReasoning,
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      };
      addMessage(finalMessage);
    }

    setStreamingMessage('');
    setStreamingReasoning('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ margin: 0 }}>小帅旅游助手</h2>
        <p style={{ margin: '4px 0 0 0', color: '#666' }}>为您提供个性化的旅游推荐和路线规划</p>
      </div>

      <div style={{ flex: 1, overflow: 'auto', marginBottom: '16px' }}>
        {/* 显示已完成的对话消息 */}
        <MessageList
          messages={messages}
          reasoningExpanded={reasoningExpanded}
          onToggleReasoning={toggleReasoning}
        />

        {/* 当前思考过程（默认折叠，点击才显示） */}
        {isThinking && (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            marginBottom: '8px'
          }}>
            <Card
              style={{
                width: '100%',
                background: '#fafafa',
                borderRadius: '8px',
                border: '1px dashed #d9d9d9',
              }}
              bodyStyle={{ padding: '12px 16px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', color: '#999' }}>
                <span style={{
                  display: 'inline-block',
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  border: '2px solid #722ed1',
                  borderTopColor: 'transparent',
                  animation: 'spin 1s linear infinite'
                }} />
                <span style={{ fontSize: '13px' }}>深度思考中{loadingDots}</span>
              </div>
            </Card>
            <style>{`
              @keyframes spin {
                to { transform: rotate(360deg); }
              }
            `}</style>
          </div>
        )}

        {/* 当前回答（流式显示） */}
        {streamingMessage && (
          <MessageList
            messages={[]}
            streamingMessage={streamingMessage}
            isThinking={false}
          />
        )}

        {/* 错误信息 */}
        {error && (
          <div style={{ color: 'red', padding: '12px', background: '#fff2f0', borderRadius: '8px', marginBottom: '8px' }}>
            {error}
          </div>
        )}

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
