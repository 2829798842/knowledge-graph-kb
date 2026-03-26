/**
 * Model-config panel.
 */

import {
  MODEL_PROVIDER_BASE_URLS,
  MODEL_PROVIDER_OPTIONS,
  get_api_key_source_label,
} from '../../shared/config/ui_constants';
import type { ModelConfigurationDraft, ModelProvider } from '../../shared/types/knowledge_base_types';
import { use_model_config } from '../hooks/use_model_config';
import '../styles/model_config_panel.css';

function update_provider(
  current_form: ModelConfigurationDraft,
  next_provider: ModelProvider,
): ModelConfigurationDraft {
  const previous_default_base_url: string = MODEL_PROVIDER_BASE_URLS[current_form.provider as ModelProvider] ?? '';
  const next_default_base_url: string = MODEL_PROVIDER_BASE_URLS[next_provider] ?? '';
  const should_replace_base_url =
    !current_form.base_url.trim() || current_form.base_url.trim() === previous_default_base_url;

  return {
    ...current_form,
    provider: next_provider,
    base_url: should_replace_base_url ? next_default_base_url : current_form.base_url,
    clear_api_key: false,
  };
}

function get_test_status_label(result: boolean | undefined, exists: boolean): string {
  if (!exists) {
    return '未测试';
  }
  return result ? '连接正常' : '连接失败';
}

export function ModelConfigPanel() {
  const {
    model_configuration,
    model_configuration_form,
    model_configuration_test_result,
    has_unsaved_model_config_changes,
    is_model_configuration_loading,
    is_saving_model_configuration,
    is_testing_model_configuration,
    set_model_configuration_form,
    refresh_model_configuration,
    save_model_configuration,
    run_model_configuration_test,
  } = use_model_config();

  const selected_provider =
    MODEL_PROVIDER_OPTIONS.find((option) => option.id === model_configuration_form.provider) ?? MODEL_PROVIDER_OPTIONS[0];
  const saved_provider =
    MODEL_PROVIDER_OPTIONS.find((item) => item.id === model_configuration?.provider) ?? null;
  const has_saved_api_key: boolean = model_configuration?.has_api_key ?? false;
  const has_typed_api_key: boolean = model_configuration_form.api_key.trim().length > 0;

  return (
    <section className='kb-panel kb-model-config-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>模型配置</h2>
          <p>把提供商、模型和密钥收在一个安静的配置面板里，保存后后续导入和检索会直接使用这里的设置。</p>
        </div>
      </header>

      <div className='kb-model-shell'>
        <div className='kb-model-main'>
          <div className='kb-detail-card kb-model-stage'>
            <div className='kb-model-hero'>
              <span className='kb-context-label'>Provider</span>
              <h3>{selected_provider.label}</h3>
              <p>{selected_provider.description}</p>
            </div>

            <div className='kb-mode-tabs'>
              {MODEL_PROVIDER_OPTIONS.map((option) => (
                <button
                  className={`kb-pill-button ${model_configuration_form.provider === option.id ? 'is-active' : ''}`}
                  key={option.id}
                  onClick={() =>
                    set_model_configuration_form((current_form) => update_provider(current_form, option.id))
                  }
                  type='button'
                >
                  {option.label}
                </button>
              ))}
            </div>

            <div className='kb-detail-card kb-model-form-card'>
              <div className='kb-section-header'>
                <div>
                  <span className='kb-context-label'>Configuration</span>
                  <h3>连接参数</h3>
                  <p>只保留最核心的四项：接口地址、通用模型、嵌入模型和 API Key。</p>
                </div>
              </div>

              <div className='kb-form-grid'>
                <label className='kb-form-field'>
                  <span>Base URL</span>
                  <input
                    onChange={(event) =>
                      set_model_configuration_form((current_form) => ({
                        ...current_form,
                        base_url: event.target.value,
                      }))
                    }
                    placeholder={selected_provider.base_url || '请输入兼容 OpenAI 的接口地址'}
                    value={model_configuration_form.base_url}
                  />
                </label>

                <label className='kb-form-field'>
                  <span>通用模型</span>
                  <input
                    onChange={(event) =>
                      set_model_configuration_form((current_form) => ({
                        ...current_form,
                        llm_model: event.target.value,
                      }))
                    }
                    placeholder='例如 gpt-5.4-mini'
                    value={model_configuration_form.llm_model}
                  />
                </label>

                <label className='kb-form-field'>
                  <span>嵌入模型</span>
                  <input
                    onChange={(event) =>
                      set_model_configuration_form((current_form) => ({
                        ...current_form,
                        embedding_model: event.target.value,
                      }))
                    }
                    placeholder='例如 text-embedding-3-large'
                    value={model_configuration_form.embedding_model}
                  />
                </label>

                <label className='kb-form-field kb-form-field-wide'>
                  <span>API Key</span>
                  <input
                    onChange={(event) =>
                      set_model_configuration_form((current_form) => ({
                        ...current_form,
                        api_key: event.target.value,
                        clear_api_key: false,
                      }))
                    }
                    placeholder={has_saved_api_key ? '留空则继续使用已保存的 API Key' : '请输入可用的 API Key'}
                    type='password'
                    value={model_configuration_form.api_key}
                  />
                </label>
              </div>

              <label className='kb-check-field'>
                <input
                  checked={model_configuration_form.clear_api_key}
                  disabled={!has_saved_api_key && !has_typed_api_key}
                  onChange={(event) =>
                    set_model_configuration_form((current_form) => ({
                      ...current_form,
                      clear_api_key: event.target.checked,
                      api_key: event.target.checked ? '' : current_form.api_key,
                    }))
                  }
                  type='checkbox'
                />
                <span>保存时清除已保存的 API Key</span>
              </label>

              <div className='kb-meta-strip'>
                <span className='kb-meta-pill'>{has_unsaved_model_config_changes ? '有未保存变更' : '配置已同步'}</span>
                <span className='kb-meta-pill'>{`密钥来源 ${get_api_key_source_label(model_configuration?.api_key_source ?? 'none')}`}</span>
                {model_configuration?.api_key_preview ? (
                  <span className='kb-meta-pill'>{`已保存密钥 ${model_configuration.api_key_preview}`}</span>
                ) : null}
              </div>

              <div className='kb-button-row'>
                <button
                  className='kb-primary-button'
                  disabled={is_saving_model_configuration || is_model_configuration_loading}
                  onClick={() => void save_model_configuration()}
                  type='button'
                >
                  {is_saving_model_configuration ? '保存中...' : '保存配置'}
                </button>

                <button
                  className='kb-secondary-button'
                  disabled={is_testing_model_configuration || is_saving_model_configuration}
                  onClick={() => void run_model_configuration_test()}
                  type='button'
                >
                  {is_testing_model_configuration ? '测试中...' : '测试连通性'}
                </button>

                <button
                  className='kb-secondary-button'
                  disabled={is_model_configuration_loading}
                  onClick={() => void refresh_model_configuration()}
                  type='button'
                >
                  重新加载
                </button>
              </div>

              <p className='kb-helper-text'>
                如果切换嵌入模型，系统会清空现有向量索引，后续需要重新导入内容才能恢复向量检索。
              </p>
            </div>
          </div>
        </div>

        <aside className='kb-model-rail'>
          <div className='kb-detail-card'>
            <span className='kb-context-label'>Saved Configuration</span>
            <h3>当前生效配置</h3>
            <p>{model_configuration?.notice ?? '保存后新配置会立即作用于后续导入、问答和向量化。'}</p>

            <div className='kb-model-status-grid'>
              <div className='kb-model-status-row'>
                <span>提供商</span>
                <strong>{saved_provider?.label ?? '--'}</strong>
              </div>
              <div className='kb-model-status-row'>
                <span>Base URL</span>
                <strong>{model_configuration?.base_url || '--'}</strong>
              </div>
              <div className='kb-model-status-row'>
                <span>通用模型</span>
                <strong>{model_configuration?.llm_model || '--'}</strong>
              </div>
              <div className='kb-model-status-row'>
                <span>嵌入模型</span>
                <strong>{model_configuration?.embedding_model || '--'}</strong>
              </div>
            </div>

            <div className='kb-meta-strip'>
              <span className='kb-meta-pill'>
                {model_configuration?.has_api_key ? '已检测到可用 API Key' : '当前没有可用 API Key'}
              </span>
              {model_configuration?.reindex_required ? <span className='kb-meta-pill'>需要重新导入向量数据</span> : null}
            </div>
          </div>

          <div className='kb-detail-card'>
            <span className='kb-context-label'>Connection Test</span>
            <h3>连通性测试</h3>
            <p>{model_configuration_test_result?.message ?? '建议在保存前先测试一次，确认通用模型和嵌入模型都能访问。'}</p>

            <div className='kb-model-test-status'>
              <div className={`kb-model-test-row ${model_configuration_test_result?.llm_ok ? 'is-ok' : 'is-idle'}`}>
                <span>通用模型</span>
                <strong>{get_test_status_label(model_configuration_test_result?.llm_ok, Boolean(model_configuration_test_result))}</strong>
              </div>

              <div
                className={`kb-model-test-row ${model_configuration_test_result?.embedding_ok ? 'is-ok' : 'is-idle'}`}
              >
                <span>嵌入模型</span>
                <strong>
                  {get_test_status_label(
                    model_configuration_test_result?.embedding_ok,
                    Boolean(model_configuration_test_result),
                  )}
                </strong>
              </div>
            </div>
          </div>

          <div className='kb-detail-card'>
            <span className='kb-context-label'>Workflow</span>
            <h3>建议流程</h3>
            <div className='kb-model-steps'>
              <div className='kb-model-step'>1. 先选择提供商并填写模型与接口地址。</div>
              <div className='kb-model-step'>2. 补充 API Key，确认是否需要清除旧密钥。</div>
              <div className='kb-model-step'>3. 先测试连通性，通过后再保存。</div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
