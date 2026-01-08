import React from 'react';
import { Select, Spin, message } from 'antd';
import { RobotOutlined } from '@ant-design/icons';
import { useAppContext } from '../context/AppContext';

const { Option } = Select;

const ModelSelector: React.FC = () => {
  const {
    availableModels,
    currentModelId,
    setCurrentModelId,
    loadingModels,
  } = useAppContext();

  const [switching, setSwitching] = React.useState(false);

  const handleChange = async (value: string) => {
    try {
      setSwitching(true);
      await setCurrentModelId(value);
      const model = availableModels.find(m => m.model_id === value);
      message.success(`已切换到 ${model?.name || value}`);
    } catch (error) {
      message.error('模型切换失败，请重试');
      console.error('模型切换错误:', error);
    } finally {
      setSwitching(false);
    }
  };

  if (loadingModels) {
    return (
      <div style={{
        width: 200,
        height: 32,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '4px 12px',
        border: '1px solid #d9d9d9',
        borderRadius: '6px'
      }}>
        <RobotOutlined style={{ color: '#1890ff' }} />
        <Spin size="small" />
        <span style={{ fontSize: '14px', color: '#999' }}>加载中...</span>
      </div>
    );
  }

  return (
    <Select
      value={currentModelId}
      onChange={handleChange}
      style={{ width: 200 }}
      placeholder="选择模型"
      suffixIcon={<RobotOutlined />}
      loading={switching}
      disabled={loadingModels || availableModels.length === 0 || switching}
    >
      {availableModels.map((model) => (
        <Option key={model.model_id} value={model.model_id}>
          {model.name}
        </Option>
      ))}
    </Select>
  );
};

export default ModelSelector;
