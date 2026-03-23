/**
 * 运行期模型配置面板。
 */

import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';

import {
  MODEL_PROVIDER_BASE_URLS,
  MODEL_PROVIDER_OPTIONS,
} from '../../constants/knowledge_base_constants';
import type {
  ModelConfiguration,
  ModelConfigurationTestRequest,
  ModelConfigurationTestResult,
  ModelConfigurationUpdateRequest,
  ModelProvider,
} from '../../types/knowledge_base';

interface ModelConfigPanelProps {
  model_configuration: ModelConfiguration | null;
  model_configuration_test_result: ModelConfigurationTestResult | null;
  is_loading: boolean;
  is_saving: boolean;
  is_testing: boolean;
  save_model_configuration: (payload: ModelConfigurationUpdateRequest) => Promise<void>;
  test_model_configuration: (payload: ModelConfigurationTestRequest) => Promise<void>;
}

function get_api_key_status_text(model_configuration: ModelConfiguration | null): string {
  if (!model_configuration?.has_api_key) {
    return '当前还没有可用的 API Key。';
  }
  if (model_configuration.api_key_source === 'saved') {
    return `已保存本地密钥：${model_configuration.api_key_preview ?? '已配置'}`;
  }
  if (model_configuration.api_key_source === 'environment') {
    return `当前使用环境变量密钥：${model_configuration.api_key_preview ?? '已配置'}`;
  }
  return '当前还没有可用的 API Key。';
}

function get_test_result_class_name(result: ModelConfigurationTestResult | null): string {
  if (!result) {
    return 'panel-note';
  }
  return result.llm_ok && result.embedding_ok ? 'panel-note panel-note-success' : 'panel-note panel-note-warning';
}

export function ModelConfigPanel(props: ModelConfigPanelProps) {
  const {
    model_configuration,
    model_configuration_test_result,
    is_loading,
    is_saving,
    is_testing,
    save_model_configuration,
    test_model_configuration,
  } = props;
  const [provider, set_provider] = useState<ModelProvider>('openai');
  const [base_url, set_base_url] = useState<string>(MODEL_PROVIDER_BASE_URLS.openai);
  const [llm_model, set_llm_model] = useState<string>('gpt-5.4-mini');
  const [embedding_model, set_embedding_model] = useState<string>('text-embedding-3-large');
  const [api_key, set_api_key] = useState<string>('');

  useEffect(() => {
    if (!model_configuration) {
      return;
    }
    set_provider(model_configuration.provider);
    set_base_url(model_configuration.base_url);
    set_llm_model(model_configuration.llm_model);
    set_embedding_model(model_configuration.embedding_model);
    set_api_key('');
  }, [model_configuration]);

  function handle_provider_change(event: ChangeEvent<HTMLSelectElement>): void {
    const next_provider: ModelProvider = event.target.value as ModelProvider;
    set_provider(next_provider);
    set_base_url(next_provider === 'custom' ? '' : MODEL_PROVIDER_BASE_URLS[next_provider]);
  }

  async function handle_submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await save_model_configuration({
      provider,
      base_url: base_url.trim(),
      llm_model: llm_model.trim(),
      embedding_model: embedding_model.trim(),
      api_key: api_key.trim() || undefined,
    });
    set_api_key('');
  }

  async function handle_clear_api_key(): Promise<void> {
    await save_model_configuration({
      provider,
      base_url: base_url.trim(),
      llm_model: llm_model.trim(),
      embedding_model: embedding_model.trim(),
      clear_api_key: true,
    });
    set_api_key('');
  }

  async function handle_test_connection(): Promise<void> {
    await test_model_configuration({
      provider,
      base_url: base_url.trim(),
      llm_model: llm_model.trim(),
      embedding_model: embedding_model.trim(),
      api_key: api_key.trim() || undefined,
      use_saved_api_key: !api_key.trim(),
    });
  }

  const can_submit: boolean = Boolean(base_url.trim()) && Boolean(llm_model.trim()) && Boolean(embedding_model.trim());
  const can_clear_key: boolean = model_configuration?.api_key_source === 'saved';

  return (
    <aside className='panel'>
      <header className='panel-header'>
        <h2>模型配置</h2>
        <p>统一管理 API 供应商、Base URL、通用模型、嵌入模型，以及本地保存的密钥。</p>
      </header>

      <form className='form-stack' onSubmit={(event) => void handle_submit(event)}>
        <label className='form-field'>
          <span>API 供应商</span>
          <select value={provider} onChange={handle_provider_change}>
            {MODEL_PROVIDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className='form-field'>
          <span>Base URL</span>
          <input
            type='text'
            value={base_url}
            placeholder='https://api.example.com/v1'
            onChange={(event) => set_base_url(event.target.value)}
          />
        </label>

        <label className='form-field'>
          <span>通用模型</span>
          <input
            type='text'
            value={llm_model}
            placeholder='gpt-5.4-mini'
            onChange={(event) => set_llm_model(event.target.value)}
          />
        </label>

        <label className='form-field'>
          <span>嵌入模型</span>
          <input
            type='text'
            value={embedding_model}
            placeholder='text-embedding-3-large'
            onChange={(event) => set_embedding_model(event.target.value)}
          />
        </label>

        <label className='form-field'>
          <span>API Key</span>
          <input
            type='password'
            value={api_key}
            placeholder={model_configuration?.has_api_key ? '留空可继续使用当前已保存密钥' : '输入新的 API Key'}
            autoComplete='off'
            onChange={(event) => set_api_key(event.target.value)}
          />
        </label>

        <p className='helper-text'>{get_api_key_status_text(model_configuration)}</p>
        <p className='panel-note'>新保存的 API Key 会加密后再写入本地数据库。</p>
        <p className='panel-note'>更换嵌入模型后，现有向量索引会被清空，需要重新导入文档才能恢复检索。</p>

        <div className='button-row'>
          <button className='primary-button' disabled={!can_submit || is_loading || is_saving} type='submit'>
            {is_saving ? '正在保存配置...' : '保存模型配置'}
          </button>
          <button
            className='ghost-button'
            disabled={!can_submit || is_loading || is_testing}
            type='button'
            onClick={() => void handle_test_connection()}
          >
            {is_testing ? '正在测试连接...' : '测试连接'}
          </button>
          <button
            className='ghost-button'
            disabled={!can_clear_key || is_loading || is_saving}
            type='button'
            onClick={() => void handle_clear_api_key()}
          >
            清除已保存密钥
          </button>
        </div>
      </form>

      {model_configuration_test_result ? (
        <div className={get_test_result_class_name(model_configuration_test_result)}>
          <strong>测试结果</strong>
          <span>
            通用模型：{model_configuration_test_result.llm_ok ? '可用' : '失败'} / 嵌入模型：
            {model_configuration_test_result.embedding_ok ? '可用' : '失败'}
          </span>
          <span>{model_configuration_test_result.message}</span>
        </div>
      ) : null}
    </aside>
  );
}
