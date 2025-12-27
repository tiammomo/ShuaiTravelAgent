import React, { useState } from 'react';
import { Card, Tag } from 'antd';
import { Message } from '../types';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import { BulbOutlined, DownOutlined, UpOutlined } from '@ant-design/icons';

interface Props {
  messages: Message[];
  streamingMessage?: string;
  loadingDots?: string;
  isThinking?: boolean;
  thinkingContent?: string;
  // 支持展开/折叠的状态管理
  reasoningExpanded?: Record<string, boolean>;
  onToggleReasoning?: (messageId: string) => void;
}

// 清理文本中的多余空行和格式问题
const cleanContent = (content: string): string => {
  if (!content) return '';
  return content
    // 移除连续的空行
    .replace(/\n{2,}/g, '\n')
    // 移除行尾空格
    .replace(/[ \t]+$/gm, '')
    .trim();
};

// 自定义Markdown组件渲染
const markdownComponents: Components = {
  p: ({ children }) => <p style={{ margin: 0, padding: 0 }}>{children}</p>,
  li: ({ children }) => <li style={{ margin: 0, padding: 0, lineHeight: 1.6 }}>{children}</li>,
  h1: ({ children }) => <h1 style={{ margin: '4px 0 2px 0', fontSize: '1.5em', fontWeight: 600 }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ margin: '4px 0 2px 0', fontSize: '1.3em', fontWeight: 600 }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ margin: '4px 0 2px 0', fontSize: '1.1em', fontWeight: 600 }}>{children}</h3>,
  ol: ({ children }) => <ol style={{ margin: '2px 0', paddingLeft: '20px' }}>{children}</ol>,
  ul: ({ children }) => <ul style={{ margin: '2px 0', paddingLeft: '20px' }}>{children}</ul>,
};

// 可折叠的思考过程组件
interface ReasoningBlockProps {
  reasoning: string;
  messageId: string;
  isExpanded: boolean;
  onToggle: (messageId: string) => void;
  isStreaming?: boolean;
}

const ReasoningBlock: React.FC<ReasoningBlockProps> = ({
  reasoning,
  messageId,
  isExpanded,
  onToggle,
  isStreaming = false
}) => {
  if (!reasoning) return null;

  return (
    <div
      style={{
        marginBottom: '8px',
        background: '#fafafa',
        borderRadius: '8px',
        border: '1px solid #e8e8e8',
        overflow: 'hidden'
      }}
    >
      {/* 头部 - 可点击展开/折叠 */}
      <div
        onClick={() => onToggle(messageId)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '8px 12px',
          cursor: 'pointer',
          background: '#f5f5f5',
          borderBottom: isExpanded ? '1px solid #e8e8e8' : 'none',
          userSelect: 'none'
        }}
      >
        <BulbOutlined
          style={{
            color: isStreaming ? '#722ed1' : '#52c41a',
            marginRight: '8px',
            fontSize: '14px'
          }}
        />
        <span style={{ fontSize: '13px', color: '#666', flex: 1 }}>
          {isStreaming ? '思考中...' : '深度思考'}
        </span>
        {isExpanded ? (
          <UpOutlined style={{ color: '#999', fontSize: '12px' }} />
        ) : (
          <DownOutlined style={{ color: '#999', fontSize: '12px' }} />
        )}
      </div>

      {/* 展开后的内容 */}
      {isExpanded && (
        <div
          style={{
            padding: '12px',
            background: '#fff',
            fontFamily: 'monospace',
            fontSize: '12px',
            lineHeight: '1.7',
            whiteSpace: 'pre-wrap',
            maxHeight: '300px',
            overflow: 'auto'
          }}
        >
          <ReactMarkdown components={markdownComponents}>
            {cleanContent(reasoning)}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
};

// 单条消息组件
const MessageItem: React.FC<{
  msg: Message;
  reasoningExpanded: Record<string, boolean>;
  onToggleReasoning: (messageId: string) => void;
}> = ({ msg, reasoningExpanded, onToggleReasoning }) => {
  const isUser = msg.role === 'user';
  const messageId = `msg_${msg.timestamp}_${msg.content.slice(0, 10)}`;
  const isExpanded = reasoningExpanded[messageId] ?? false; // 默认折叠

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        marginBottom: '8px'
      }}
    >
      <Card
        style={{
          width: '100%',
          background: isUser
            ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
            : '#fff',
          color: isUser ? 'white' : '#262730',
          borderRadius: '12px',
          border: isUser ? 'none' : '1px solid #e8e8e8',
        }}
        bodyStyle={{ padding: '16px' }}
      >
        {/* 用户头像 */}
        <div style={{
          fontSize: '13px',
          marginBottom: '8px',
          opacity: 0.8,
          fontWeight: 500
        }}>
          {isUser ? '你' : '小帅助手'}
        </div>

        {/* 思考过程（仅助手消息，如果有reasoning） */}
        {!isUser && msg.reasoning && (
          <ReasoningBlock
            reasoning={msg.reasoning}
            messageId={messageId}
            isExpanded={isExpanded}
            onToggle={onToggleReasoning}
          />
        )}

        {/* 消息内容 */}
        <div style={{ lineHeight: 1.7 }}>
          <ReactMarkdown components={markdownComponents}>
            {cleanContent(msg.content)}
          </ReactMarkdown>
        </div>

        {/* 时间戳 */}
        <div style={{
          fontSize: '11px',
          marginTop: '8px',
          opacity: 0.6,
          textAlign: 'right'
        }}>
          {msg.timestamp}
        </div>
      </Card>
    </div>
  );
};

const MessageList: React.FC<Props> = ({
  messages,
  streamingMessage,
  loadingDots,
  isThinking,
  reasoningExpanded = {},
  onToggleReasoning
}) => {
  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', width: '100%' }}>
      {messages.map((msg, index) => (
        <MessageItem
          key={index}
          msg={msg}
          reasoningExpanded={reasoningExpanded}
          onToggleReasoning={onToggleReasoning || (() => {})}
        />
      ))}

      {/* 流式思考过程 - 默认折叠，点击才显示内容 */}
      {isThinking && thinkingContent && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            marginBottom: '8px'
          }}
        >
          <Card
            style={{
              width: '100%',
              background: '#fafafa',
              borderRadius: '12px',
              border: '1px dashed #d9d9d9',
            }}
            bodyStyle={{ padding: '12px 16px' }}
          >
            {/* 头部 - 始终显示加载状态 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              color: '#999',
              cursor: 'pointer'
            }}>
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

      {/* 流式回答内容 */}
      {streamingMessage && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            marginBottom: '8px'
          }}
        >
          <Card
            style={{
              width: '100%',
              background: '#fff',
              borderRadius: '12px',
              border: '1px solid #e8e8e8',
            }}
            bodyStyle={{ padding: '16px' }}
          >
            <div style={{ fontSize: '13px', color: '#666', marginBottom: '8px', fontWeight: 500 }}>
              小帅助手
            </div>
            <div style={{ lineHeight: 1.7 }}>
              <ReactMarkdown components={markdownComponents}>
                {cleanContent(streamingMessage)}
              </ReactMarkdown>
            </div>
            {loadingDots && (
              <span style={{ color: '#999', fontSize: '12px', marginLeft: '4px' }}>
                {loadingDots}
              </span>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};

export default MessageList;
