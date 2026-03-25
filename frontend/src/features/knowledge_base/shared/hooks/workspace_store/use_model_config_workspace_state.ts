/**
 * Model-configuration state and actions.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';

import {
  fetch_model_configuration,
  test_model_configuration,
  update_model_configuration,
} from '../../api/model_config_api';
import { kb_query_keys } from '../../api/query_client';
import type {
  ModelConfigurationDraft,
  ModelConfigurationRecord,
  ModelConfigurationTestRecord,
  WorkspaceTab,
} from '../../types/knowledge_base_types';

const MODEL_PROVIDER_BASE_URLS: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  openrouter: 'https://openrouter.ai/api/v1',
  siliconflow: 'https://api.siliconflow.cn/v1',
  custom: '',
};

const DEFAULT_MODEL_CONFIGURATION_FORM: ModelConfigurationDraft = {
  provider: 'openai',
  base_url: MODEL_PROVIDER_BASE_URLS.openai,
  llm_model: '',
  embedding_model: '',
  api_key: '',
  clear_api_key: false,
};

function to_model_configuration_form(config: ModelConfigurationRecord): ModelConfigurationDraft {
  return {
    provider: config.provider,
    base_url: config.base_url,
    llm_model: config.llm_model,
    embedding_model: config.embedding_model,
    api_key: '',
    clear_api_key: false,
  };
}

function build_form_signature(form: ModelConfigurationDraft): string {
  return JSON.stringify({
    provider: form.provider.trim(),
    base_url: form.base_url.trim(),
    llm_model: form.llm_model.trim(),
    embedding_model: form.embedding_model.trim(),
    api_key: form.api_key.trim(),
    clear_api_key: form.clear_api_key,
  });
}

interface ModelConfigWorkspaceStateProps {
  active_workspace: WorkspaceTab;
  set_message: Dispatch<SetStateAction<string>>;
  set_error: Dispatch<SetStateAction<string | null>>;
}

export function use_model_config_workspace_state(props: ModelConfigWorkspaceStateProps) {
  const { active_workspace, set_message, set_error } = props;
  const query_client = useQueryClient();
  const [has_opened_model_config, set_has_opened_model_config] = useState<boolean>(active_workspace === 'config');
  const [model_configuration_form, set_model_configuration_form] = useState<ModelConfigurationDraft>(
    DEFAULT_MODEL_CONFIGURATION_FORM,
  );
  const [saved_form_signature, set_saved_form_signature] = useState<string>(
    build_form_signature(DEFAULT_MODEL_CONFIGURATION_FORM),
  );
  const [model_configuration_test_result, set_model_configuration_test_result] =
    useState<ModelConfigurationTestRecord | null>(null);

  useEffect(() => {
    if (active_workspace === 'config') {
      set_has_opened_model_config(true);
    }
  }, [active_workspace]);

  const model_configuration_query = useQuery({
    queryKey: kb_query_keys.model_config(),
    queryFn: fetch_model_configuration,
    enabled: has_opened_model_config,
  });

  useEffect(() => {
    if (!model_configuration_query.data) {
      return;
    }

    const next_form = to_model_configuration_form(model_configuration_query.data);
    set_model_configuration_form(next_form);
    set_saved_form_signature(build_form_signature(next_form));
    set_model_configuration_test_result(null);
  }, [model_configuration_query.data]);

  useEffect(() => {
    if (model_configuration_query.error) {
      set_error((model_configuration_query.error as Error).message);
    }
  }, [model_configuration_query.error, set_error]);

  const save_model_configuration_mutation = useMutation({
    mutationFn: (payload: ModelConfigurationDraft) =>
      update_model_configuration({
        provider: payload.provider.trim(),
        base_url: payload.base_url.trim(),
        llm_model: payload.llm_model.trim(),
        embedding_model: payload.embedding_model.trim(),
        api_key: payload.clear_api_key ? null : payload.api_key.trim() || null,
        clear_api_key: payload.clear_api_key,
      }),
    onSuccess: (result) => {
      query_client.setQueryData(kb_query_keys.model_config(), result);
      set_message(
        result.notice ?? (result.reindex_required ? '模型配置已保存，现有向量索引已重置。' : '模型配置已保存。'),
      );
      set_error(null);
      set_model_configuration_test_result(null);
    },
    onError: (config_error) => {
      set_error((config_error as Error).message);
    },
  });

  const test_model_configuration_mutation = useMutation({
    mutationFn: (payload: ModelConfigurationDraft) =>
      test_model_configuration({
        provider: payload.provider.trim(),
        base_url: payload.base_url.trim(),
        llm_model: payload.llm_model.trim(),
        embedding_model: payload.embedding_model.trim(),
        api_key: payload.api_key.trim() || null,
        use_saved_api_key: !payload.api_key.trim() && !payload.clear_api_key,
      }),
    onSuccess: (result) => {
      set_model_configuration_test_result(result);
      set_message(result.message);
      set_error(null);
    },
    onError: (config_error) => {
      set_error((config_error as Error).message);
    },
  });

  async function refresh_model_configuration(): Promise<void> {
    try {
      set_has_opened_model_config(true);
      await query_client.invalidateQueries({ queryKey: kb_query_keys.model_config() });
      await query_client.refetchQueries({ queryKey: kb_query_keys.model_config() });
    } catch (refresh_error) {
      set_error((refresh_error as Error).message);
    }
  }

  async function save_model_configuration_form(): Promise<void> {
    await save_model_configuration_mutation.mutateAsync(model_configuration_form);
  }

  async function run_model_configuration_test(): Promise<void> {
    await test_model_configuration_mutation.mutateAsync(model_configuration_form);
  }

  const has_unsaved_model_config_changes: boolean = useMemo(
    () => build_form_signature(model_configuration_form) !== saved_form_signature,
    [model_configuration_form, saved_form_signature],
  );

  return {
    model_configuration: (model_configuration_query.data ?? null) as ModelConfigurationRecord | null,
    model_configuration_form,
    set_model_configuration_form,
    refresh_model_configuration,
    save_model_configuration: save_model_configuration_form,
    run_model_configuration_test,
    model_configuration_test_result,
    has_unsaved_model_config_changes,
    is_model_configuration_loading: model_configuration_query.isLoading || model_configuration_query.isFetching,
    is_saving_model_configuration: save_model_configuration_mutation.isPending,
    is_testing_model_configuration: test_model_configuration_mutation.isPending,
  };
}
