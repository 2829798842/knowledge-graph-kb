/**
 * Model-config workspace slice.
 */

import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';

export function use_model_config() {
  const workspace = use_knowledge_base_workspace_context();

  return {
    model_configuration: workspace.model_configuration,
    model_configuration_form: workspace.model_configuration_form,
    model_configuration_test_result: workspace.model_configuration_test_result,
    has_unsaved_model_config_changes: workspace.has_unsaved_model_config_changes,
    is_model_configuration_loading: workspace.is_model_configuration_loading,
    is_saving_model_configuration: workspace.is_saving_model_configuration,
    is_testing_model_configuration: workspace.is_testing_model_configuration,
    set_model_configuration_form: workspace.set_model_configuration_form,
    refresh_model_configuration: workspace.refresh_model_configuration,
    save_model_configuration: workspace.save_model_configuration,
    run_model_configuration_test: workspace.run_model_configuration_test,
  };
}

