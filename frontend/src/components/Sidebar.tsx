import React, { useState } from 'react';
import { Button, Input, Space, List, Card, message as antMessage, Modal, Select, Spin } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ApiOutlined,
  EditOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { useAppContext } from '../context/AppContext';
import { apiService } from '../services/api';
import { SessionInfo } from '../types';

const { Option } = Select;

const Sidebar: React.FC = () => {
  const {
    config,
    setConfig,
    currentSessionId,
    switchSession,
    availableModels,
    currentModelId,
    setCurrentModelId,
    loadingModels,
    sessions,
    refreshSessions,
    clearMessages,
  } = useAppContext();

  const [apiBase, setApiBase] = useState(config.apiBase);
  const [loading, setLoading] = useState(false);
  const [switchingModel, setSwitchingModel] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');

  // 创建新会话
  const handleCreateSession = async () => {
    try {
      setLoading(true);
      const data = await apiService.createSession();
      // 使用switchSession切换到新会话，保留原会话消息
      switchSession(data.session_id);
      // 刷新会话列表
      await refreshSessions();
      antMessage.success('新会话已创建');
    } catch (error) {
      antMessage.error('创建会话失败');
    } finally {
      setLoading(false);
    }
  };

  // 删除会话
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await apiService.deleteSession(sessionId);
      if (sessionId === currentSessionId) {
        // 如果删除的是当前会话，切换到空会话
        switchSession(null);
      }
      await refreshSessions();
      antMessage.success('会话已删除');
    } catch (error) {
      antMessage.error('删除失败');
    }
  };

  // 切换会话
  const handleSwitchSession = (sessionId: string) => {
    switchSession(sessionId);  // 使用switchSession保留消息
  };

  // 开始编辑会话名称
  const handleStartEdit = (session: SessionInfo) => {
    setEditingSessionId(session.session_id);
    setEditingName(session.name || `会话 ${session.session_id.slice(0, 8)}`);
  };

  // 取消编辑
  const handleCancelEdit = () => {
    setEditingSessionId(null);
    setEditingName('');
  };

  // 保存会话名称
  const handleSaveEdit = async () => {
    if (!editingSessionId || !editingName.trim()) return;

    try {
      await apiService.updateSessionName(editingSessionId, editingName.trim());
      await refreshSessions();
      setEditingSessionId(null);
      setEditingName('');
      antMessage.success('会话名称已更新');
    } catch (error) {
      antMessage.error('更新失败');
    }
  };

  // 健康检查
  const handleHealthCheck = async () => {
    try {
      const data = await apiService.checkHealth();
      antMessage.success(`✅ 连接成功\n\nAgent: ${data.agent}\n版本: ${data.version}`);
    } catch (error) {
      antMessage.error('❌ 无法连接到服务器');
    }
  };

  // 清空对话
  const handleClearChat = async () => {
    if (!currentSessionId) {
      antMessage.warning('请先创建会话');
      return;
    }

    try {
      await apiService.clearChat(currentSessionId);
      clearMessages();
      antMessage.success('对话已清空');
    } catch (error) {
      antMessage.error('清空失败');
    }
  };

  // 模型切换
  const handleModelChange = async (modelId: string) => {
    try {
      setSwitchingModel(true);
      await setCurrentModelId(modelId);
      const model = availableModels.find(m => m.model_id === modelId);
      antMessage.success(`已切换到 ${model?.name || modelId}`);
    } catch (error) {
      antMessage.error('模型切换失败，请重试');
      console.error('模型切换错误:', error);
    } finally {
      setSwitchingModel(false);
    }
  };

  return (
    <div style={{ padding: '24px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 模型选择 */}
      <Card title="🤖 AI模型" size="small" style={{ marginBottom: '16px' }}>
        {loadingModels ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0' }}>
            <RobotOutlined style={{ color: '#1890ff' }} />
            <Spin size="small" />
            <span style={{ fontSize: '14px', color: '#999' }}>加载中...</span>
          </div>
        ) : (
          <Select
            value={currentModelId}
            onChange={handleModelChange}
            style={{ width: '100%' }}
            placeholder="选择模型"
            suffixIcon={<RobotOutlined />}
            loading={switchingModel}
            disabled={availableModels.length === 0 || switchingModel}
          >
            {availableModels.map((model) => (
              <Option key={model.model_id} value={model.model_id}>
                {model.name}
              </Option>
            ))}
          </Select>
        )}
      </Card>

      {/* API配置 */}
      <Card title="⚙️ 系统配置" size="small" style={{ marginBottom: '16px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            onBlur={() => setConfig({ apiBase })}
            placeholder="API地址"
            prefix={<ApiOutlined />}
          />
          <Button onClick={handleHealthCheck} block>
            🔍 检查连接
          </Button>
        </Space>
      </Card>

      {/* 会话管理 */}
      <Card title="📝 会话管理" size="small" style={{ marginBottom: '16px' }}>
        <Space style={{ width: '100%' }}>
          <Button
            icon={<PlusOutlined />}
            onClick={handleCreateSession}
            loading={loading}
            style={{ flex: 1 }}
          >
            新建
          </Button>
          <Button onClick={handleClearChat} style={{ flex: 1 }}>
            🗑️ 清空
          </Button>
        </Space>
      </Card>

      {/* 历史会话 */}
      <Card
        title="📊 历史会话"
        size="small"
        style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, overflow: 'auto', padding: '8px' }}
      >
        <List
          dataSource={sessions}
          renderItem={(session) => (
            <List.Item
              style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}
              actions={[
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => handleStartEdit(session)}
                  title="重命名"
                />,
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteSession(session.session_id)}
                  title="删除"
                />
              ]}
            >
              <div
                onClick={() => handleSwitchSession(session.session_id)}
                style={{ cursor: 'pointer', flex: 1 }}
              >
                <div style={{ fontWeight: session.session_id === currentSessionId ? 'bold' : 'normal' }}>
                  {session.session_id === currentSessionId && <CheckCircleOutlined style={{ marginRight: '4px', color: '#52c41a' }} />}
                  {session.name || `会话 ${session.session_id.slice(0, 8)}`} ({session.message_count}条)
                </div>
                <div style={{ fontSize: '12px', color: '#999' }}>
                  🕒 {new Date(session.last_active).toLocaleString('zh-CN')}
                </div>
              </div>
            </List.Item>
          )}
        />
      </Card>

      {/* 编辑会话名称对话框 */}
      <Modal
        title="重命名会话"
        open={editingSessionId !== null}
        onOk={handleSaveEdit}
        onCancel={handleCancelEdit}
        okText="保存"
        cancelText="取消"
      >
        <Input
          value={editingName}
          onChange={(e) => setEditingName(e.target.value)}
          placeholder="请输入会话名称"
          maxLength={50}
          onPressEnter={handleSaveEdit}
        />
      </Modal>

      <div style={{ marginTop: '16px', textAlign: 'center', fontSize: '12px', color: '#999' }}>
        Powered by tiammomo
      </div>
    </div>
  );
};

export default Sidebar;
