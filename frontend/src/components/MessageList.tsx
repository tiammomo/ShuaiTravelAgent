import React, { useState } from 'react';
import { Card, Collapse, Tag } from 'antd';
import { Message } from '../types';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import { BulbOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons';

interface Props {
  messages: Message[];
  streamingMessage?: string;
  loadingDots?: string;
  isThinking?: boolean;
  thinkingContent?: string;  // 实时思考过程内容
}

const { Panel } = Collapse;

// 清理文本中的多余空行和格式问题
const cleanContent = (content: string): string => {
  return content
    // 移除连续的空行（2个或更多换行符变为1个）
    .replace(/\n{2,}/g, '\n')
    // 移除行尾空格
    .replace(/[ \t]+$/gm, '')
    // 移除开头和结尾的空白
    .trim();
};

// 自定义Markdown组件渲染，优化间距
const markdownComponents: Components = {
  // 段落：无间距
  p: ({ children }) => <p style={{ margin: 0, padding: 0 }}>{children}</p>,
  // 列表项：无间距
  li: ({ children }) => <li style={{ margin: 0, padding: 0, lineHeight: 1.4 }}>{children}</li>,
  // 标题：最小间距
  h1: ({ children }) => <h1 style={{ margin: '4px 0 2px 0', fontSize: '1.5em', fontWeight: 600, lineHeight: 1.2 }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ margin: '4px 0 2px 0', fontSize: '1.3em', fontWeight: 600, lineHeight: 1.2 }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ margin: '4px 0 2px 0', fontSize: '1.1em', fontWeight: 600, lineHeight: 1.2 }}>{children}</h3>,
  // 列表：最小间距
  ol: ({ children }) => <ol style={{ margin: '2px 0', paddingLeft: '20px' }}>{children}</ol>,
  ul: ({ children }) => <ul style={{ margin: '2px 0', paddingLeft: '20px' }}>{children}</ul>,
};

// 思考过程面板组件
const ReasoningPanel: React.FC<{ reasoning: string }> = ({ reasoning }) => {
  const [expanded, setExpanded] = useState(true);

  if (!reasoning) return null;

  return (
    <Collapse
      defaultActiveKey={['reasoning']}
      style={{ marginTop: '8px', background: '#fafafa' }}
      bordered={false}
    >
      <Panel
        key="reasoning"
        header={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BulbOutlined style={{ color: '#722ed1' }} />
            <span style={{ fontWeight: 500 }}>AI 思考过程</span>
            <Tag color="purple" style={{ marginLeft: '8px' }}>可展开查看</Tag>
          </div>
        }
        extra={
          expanded ?
            <EyeOutlined onClick={(e) => { e.stopPropagation(); setExpanded(false); }} /> :
            <EyeInvisibleOutlined onClick={(e) => { e.stopPropagation(); setExpanded(true); }} />
        }
      >
        <div style={{
          background: '#f5f5f5',
          padding: '12px',
          borderRadius: '6px',
          fontFamily: 'monospace',
          fontSize: '12px',
          lineHeight: '1.6',
          whiteSpace: 'pre-wrap',
          maxHeight: '400px',
          overflow: 'auto'
        }}>
          <ReactMarkdown>{reasoning}</ReactMarkdown>
        </div>
      </Panel>
    </Collapse>
  );
};

// 实时思考过程流显示组件
const StreamingReasoning: React.FC<{ content: string }> = ({ content }) => {
  const [expanded, setExpanded] = useState(true);

  if (!content) return null;

  return (
    <div style={{ marginTop: '8px' }}>
      <Collapse
        defaultActiveKey={['thinking']}
        style={{ background: '#fafafa' }}
        bordered={false}
      >
        <Panel
          key="thinking"
          header={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BulbOutlined style={{ color: '#722ed1', animation: 'pulse 1.5s infinite' }} />
              <span style={{ fontWeight: 500, color: '#722ed1' }}>AI 思考中...</span>
              <Tag color="processing" style={{ marginLeft: '8px' }}>实时生成</Tag>
            </div>
          }
          extra={
            expanded ?
              <EyeOutlined onClick={(e) => { e.stopPropagation(); setExpanded(false); }} /> :
              <EyeInvisibleOutlined onClick={(e) => { e.stopPropagation(); setExpanded(true); }} />
          }
        >
          <div style={{
            background: '#f0f0f0',
            padding: '12px',
            borderRadius: '6px',
            fontFamily: 'monospace',
            fontSize: '12px',
            lineHeight: '1.6',
            whiteSpace: 'pre-wrap',
            maxHeight: '300px',
            overflow: 'auto',
            borderLeft: '3px solid #722ed1'
          }}>
            {content}
          </div>
        </Panel>
      </Collapse>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
};

const MessageList: React.FC<Props> = ({ messages, streamingMessage, loadingDots, isThinking, thinkingContent }) => {
  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', width: '100%' }}>
      {messages.map((msg, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            justifyContent: 'center',
            marginBottom: '6px',
          }}
        >
          <Card
            className={`chat-message ${msg.role}`}
            style={{
              width: '100%',
              background: msg.role === 'user'
                ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                : '#f0f2f6',
              color: msg.role === 'user' ? 'white' : '#262730',
              borderRadius: '8px',
            }}
            bodyStyle={{ padding: '12px 16px' }}
          >
            <div className="chat-message-content">
              <ReactMarkdown components={markdownComponents}>
                {cleanContent(msg.content)}
              </ReactMarkdown>
            </div>

            {/* 显示思考过程（仅助手消息） */}
            {msg.role === 'assistant' && msg.reasoning && (
              <ReasoningPanel reasoning={msg.reasoning} />
            )}

            <div className="chat-message-time" style={{
              marginTop: msg.role === 'assistant' && msg.reasoning ? '8px' : '0'
            }}>{msg.timestamp}</div>
          </Card>
        </div>
      ))}

      {isThinking && (
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '6px' }}>
          <Card
            className="chat-message assistant"
            style={{
              width: '100%',
              background: '#f0f2f6',
              color: '#262730',
              borderRadius: '8px',
            }}
            bodyStyle={{ padding: '12px 16px' }}
          >
            <div className="chat-message-content" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BulbOutlined style={{ color: '#722ed1', fontSize: '16px', animation: 'pulse 1.5s infinite' }} />
              <span className="thinking-indicator">●{loadingDots || ''}</span>
              <span style={{ color: '#666' }}>正在深度思考中...</span>
            </div>
            {/* 显示实时思考过程 */}
            {thinkingContent && <StreamingReasoning content={thinkingContent} />}
          </Card>
        </div>
      )}

      {streamingMessage && (
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '6px' }}>
          <Card
            className="chat-message assistant"
            style={{
              width: '100%',
              background: '#f0f2f6',
              color: '#262730',
              borderRadius: '8px',
            }}
            bodyStyle={{ padding: '12px 16px' }}
          >
            <div className="chat-message-content">
              <ReactMarkdown components={markdownComponents}>
                {cleanContent(streamingMessage)}
              </ReactMarkdown>
            </div>
            {/* 显示动态加载指示器 */}
            <span className="thinking-indicator">●{loadingDots || ''}</span>
          </Card>
        </div>
      )}
    </div>
  );
};

// 添加全局动画样式
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
`;
if (document.head) {
  document.head.appendChild(styleSheet);
}

export default MessageList;
