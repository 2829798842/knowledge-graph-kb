import { MODEL_PROVIDER_BASE_URLS, MODEL_PROVIDER_OPTIONS, get_api_key_source_label } from '../../shared/config/ui_constants';
import type { ModelConfigurationDraft, ModelProvider } from '../../shared/types/knowledge_base_types';
import { use_model_config } from '../hooks/use_model_config';

function update_provider(current_form: ModelConfigurationDraft, next_provider: ModelProvider): ModelConfigurationDraft {
  const previous_default_base_url = MODEL_PROVIDER_BASE_URLS[current_form.provider as ModelProvider] ?? '';
  const next_default_base_url = MODEL_PROVIDER_BASE_URLS[next_provider] ?? '';
  const should_replace_base_url = !current_form.base_url.trim() || current_form.base_url.trim() === previous_default_base_url;

  return {
    ...current_form,
    provider: next_provider,
    base_url: should_replace_base_url ? next_default_base_url : current_form.base_url,
    clear_api_key: false,
  };
}

interface ModelConfigModalProps {
  open: boolean;
  on_close: () => void;
}

export function ModelConfigModal(props: ModelConfigModalProps) {
  const { open, on_close } = props;
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

  if (!open) {
    return null;
  }

  const selected_provider =
    MODEL_PROVIDER_OPTIONS.find((option) => option.id === model_configuration_form.provider) ?? MODEL_PROVIDER_OPTIONS[0];

  return (
    <div className='kb-modal-backdrop' onClick={on_close} role='presentation'>
      <section aria-modal='true' className='kb-modal kb-settings-modal' onClick={(event) => event.stopPropagation()} role='dialog'>
        <div className='kb-modal-header'>
          <div>
            <span className='kb-context-label'>Settings</span>
            <h3>API / LLM 配置</h3>
            <p>复用现有后端配置结构，把聊天和导入所需参数集中管理。</p>
          </div>
          <button className='kb-secondary-button' onClick={on_close} type='button'>
            关闭
          </button>
        </div>

        <div className='kb-mode-tabs'>
          {MODEL_PROVIDER_OPTIONS.map((option) => (
            <button
              className={`kb-pill-button ${model_configuration_form.provider === option.id ? 'is-active' : ''}`}
              key={option.id}
              onClick={() => set_model_configuration_form((current_form) => update_provider(current_form, option.id))}
              type='button'
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className='kb-detail-card'>
          <div className='kb-section-header'>
            <div>
              <h3>{selected_provider.label}</h3>
              <p>{selected_provider.description}</p>
            </div>
          </div>

          <div className='kb-form-grid'>
            <label className='kb-form-field'>
              <span>Base URL</span>
              <input
                onChange={(event) => set_model_configuration_form((current_form) => ({ ...current_form, base_url: event.target.value }))}
                placeholder={selected_provider.base_url || '请输入兼容 OpenAI 的接口地址'}
                value={model_configuration_form.base_url}
              />
            </label>

            <label className='kb-form-field'>
              <span>聊天模型</span>
              <input
                onChange={(event) => set_model_configuration_form((current_form) => ({ ...current_form, llm_model: event.target.value }))}
                placeholder='例如 gpt-5.4-mini'
                value={model_configuration_form.llm_model}
              />
            </label>

            <label className='kb-form-field'>
              <span>Embedding 模型</span>
              <input
                onChange={(event) => set_model_configuration_form((current_form) => ({ ...current_form, embedding_model: event.target.value }))}
                placeholder='例如 text-embedding-3-large'
                value={model_configuration_form.embedding_model}
              />
            </label>

            <label className='kb-form-field kb-form-field-wide'>
              <span>API Key</span>
              <input
                onChange={(event) => set_model_configuration_form((current_form) => ({ ...current_form, api_key: event.target.value, clear_api_key: false }))}
                placeholder={model_configuration?.has_api_key ? '留空则继续使用已保存的 API Key' : '请输入可用的 API Key'}
                type='password'
                value={model_configuration_form.api_key}
              />
            </label>
          </div>

          <label className='kb-check-field'>
            <input
              checked={model_configuration_form.clear_api_key}
              disabled={!model_configuration?.has_api_key && !model_configuration_form.api_key.trim()}
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
            <span className='kb-meta-pill'>{has_unsaved_model_config_changes ? '有未保存修改' : '配置已同步'}</span>
            <span className='kb-meta-pill'>{`密钥来源 ${get_api_key_source_label(model_configuration?.api_key_source ?? 'none')}`}</span>
            {model_configuration?.api_key_preview ? <span className='kb-meta-pill'>{model_configuration.api_key_preview}</span> : null}
          </div>
        </div>

        <div className='kb-detail-card'>
          <div className='kb-meta-strip'>
            <span className='kb-meta-pill'>{is_model_configuration_loading ? '正在加载配置' : '配置已加载'}</span>
            {model_configuration?.reindex_required ? <span className='kb-meta-pill'>切换 Embedding 后需要重新导入向量</span> : null}
            {model_configuration_test_result ? <span className='kb-meta-pill'>{model_configuration_test_result.message}</span> : null}
          </div>

          <div className='kb-button-row'>
            <button className='kb-primary-button' disabled={is_saving_model_configuration || is_model_configuration_loading} onClick={() => void save_model_configuration()} type='button'>
              {is_saving_model_configuration ? '保存中...' : '保存配置'}
            </button>
            <button className='kb-secondary-button' disabled={is_testing_model_configuration || is_saving_model_configuration} onClick={() => void run_model_configuration_test()} type='button'>
              {is_testing_model_configuration ? '测试中...' : '测试连通性'}
            </button>
            <button className='kb-secondary-button' disabled={is_model_configuration_loading} onClick={() => void refresh_model_configuration()} type='button'>
              重新加载
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
