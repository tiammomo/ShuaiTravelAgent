'use client';

import React from 'react';
import { Select, Tooltip, Badge } from 'antd';
import {
  ThunderboltOutlined,
  BulbOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import { ChatMode } from '@/types';

interface ChatModeSelectorProps {
  value: ChatMode;
  onChange: (value: ChatMode) => void;
  disabled?: boolean;
}

const modeOptions = [
  {
    value: 'direct',
    label: '直接模式',
    icon: <ThunderboltOutlined />,
    description: '快速响应，简单对话',
    color: '#52c41a'
  },
  {
    value: 'react',
    label: 'ReAct模式',
    icon: <BulbOutlined />,
    description: '推理+行动，深度思考',
    color: '#1890ff'
  },
  {
    value: 'plan',
    label: '规划模式',
    icon: <FileTextOutlined />,
    description: '先规划，后执行',
    color: '#722ed1'
  }
];

const ChatModeSelector: React.FC<ChatModeSelectorProps> = ({
  value = 'react',
  onChange,
  disabled = false
}) => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    }}>
      <span style={{
        fontSize: '12px',
        color: '#999',
        whiteSpace: 'nowrap'
      }}>
        对话模式:
      </span>
      <Select
        value={value}
        onChange={onChange}
        disabled={disabled}
        style={{ width: 140 }}
        size="small"
        options={modeOptions.map(option => ({
          value: option.value,
          label: (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <span style={{ color: option.color }}>
                {option.icon}
              </span>
              <span>{option.label}</span>
            </div>
          ),
          title: option.description
        }))}
      />
      <Tooltip title={modeOptions.find(m => m.value === value)?.description}>
        <Badge
          color={modeOptions.find(m => m.value === value)?.color}
          text=""
          style={{ cursor: 'help' }}
        />
      </Tooltip>
    </div>
  );
};

export default ChatModeSelector;
