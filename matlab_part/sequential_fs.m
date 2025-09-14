%% Sequential fs feature selection

% 1. Define your features (excluding targets and IDs)
all_features = aggregated_features_enriched.Properties.VariableNames;
reduced_features = setdiff(all_features, {'MeanPower', 'ExperimentID', });

% 2. Set up experiment-aware cross-validation
c = cvpartition(aggregated_features_enriched.ExperimentID, 'KFold', 5); % Experiment-aware CV
opts = statset('Display', 'iter', 'UseParallel', true);

% 3. Define RMSE scoring function
fs_func = @(X_train, y_train, X_test, y_test) ...
    sqrt(mean((predict(fitrensemble(X_train, y_train, 'Method', 'Bag'), X_test) - y_test).^2)); % RMSE

% 4. Run sequential feature selection with RMSE
[in_model, history] = sequentialfs(fs_func, ...
    aggregated_features_enriched{:, reduced_features}, ...
    aggregated_features_enriched.MeanPower, ...
    'cv', c, ...
    'options', opts, ...
    'direction', 'forward'); % 'backward' for elimination

optimal_features = reduced_features(in_model);
selected_columns = [optimal_features, {'MeanPower', 'ExperimentID'}];
aggregated_features_optimal = aggregated_features_enriched(:, selected_columns);

% Get all numeric features (excluding target and IDs)
numeric_features = aggregated_features_enriched(:, ~ismember(aggregated_features_enriched.Properties.VariableNames, ...
                  {'MeanPower', 'ExperimentID', 'LogMeanPower'}));