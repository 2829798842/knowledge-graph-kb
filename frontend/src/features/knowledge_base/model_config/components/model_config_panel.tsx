/**
 * 模型配置面板。
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
  const has_saved_api_key: boolean = model_configuration?.has_api_key ?? false;
  const has_typed_api_key: boolean = model_configuration_form.api_key.trim().length > 0;

  return (
    <section className='kb-panel kb-model-config-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>模型配置</h2>
          <p>统一管理提供商、模型、Base URL 与 API Key，保存后后续导入和检索会直接使用这里的配置。</p>
        </div>
      </header>

      <div className='kb-model-config-layout'>
        <div className='kb-detail-card kb-model-config-form'>
          <div className='kb-model-config-hero'>
            <span className='kb-context-label'>当前提供商</span>
            <h3>{selected_provider.label}</h3>
            <p>{selected_provider.description}</p>
          </div>

          <div className='kb-form-grid'>
            <label className='kb-form-field'>
              <span>提供商</span>
              <select
                onChange={(event) =>
                  set_model_configuration_form((current_form) =>
                    update_provider(current_form, event.target.value as ModelProvider),
                  )
                }
                value={model_configuration_form.provider}
              >
                {MODEL_PROVIDER_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

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
            预设提供商留空时会使用默认 Base URL；如果切换嵌入模型，系统会清空现有向量索引，需要重新导入内容。
          </p>
        </div>

        <div className='kb-result-stack kb-model-config-status'>
          <div className='kb-detail-card'>
            <span className='kb-context-label'>当前保存配置</span>
            <strong>{is_model_configuration_loading && !model_configuration ? '正在读取模型配置...' : '后端当前生效配置'}</strong>
            <p>{model_configuration?.notice ?? '保存后新配置会立即作用于后续导入、问答和向量化。'}</p>

            <div className='kb-model-status-grid'>
              <div className='kb-model-status-row'>
                <span>提供商</span>
                <strong>{MODEL_PROVIDER_OPTIONS.find((item) => item.id === model_configuration?.provider)?.label ?? '--'}</strong>
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
            <span className='kb-context-label'>连通性测试</span>
            <strong>{model_configuration_test_result ? '最近一次测试结果' : '还没有执行测试'}</strong>
            <p>{model_configuration_test_result?.message ?? '建议保存前先测试一次，确认通用模型和嵌入模型都能访问。'}</p>

            <div className='kb-model-test-status'>
              <div className={`kb-model-test-row ${model_configuration_test_result?.llm_ok ? 'is-ok' : 'is-idle'}`}>
                <span>通用模型</span>
                <strong>
                  {!model_configuration_test_result
                    ? '未测试'
                    : model_configuration_test_result.llm_ok
                      ? '连接正常'
                      : '连接失败'}
                </strong>
              </div>

              <div
                className={`kb-model-test-row ${model_configuration_test_result?.embedding_ok ? 'is-ok' : 'is-idle'}`}
              >
                <span>嵌入模型</span>
                <strong>
                  {!model_configuration_test_result
                    ? '未测试'
                    : model_configuration_test_result.embedding_ok
                      ? '连接正常'
                      : '连接失败'}
                </strong>
              </div>
            </div>
          </div>

          <div className='kb-detail-card'>
            <span className='kb-context-label'>使用说明</span>
            <strong>建议流程</strong>
            <p>先填写提供商、模型和 API Key，再执行连通性测试；确认可用后保存，后续导入和问答都会走这套配置。</p>
          </div>
        </div>
      </div>
    </section>
  );
}
