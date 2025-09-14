% Parameters
num_previous = 12; % Include previous 6 seconds (bins)

% Get all feature names (excluding targets and IDs)
base_features = setdiff(aggregated_features.Properties.VariableNames, ...
                      {'MeanPower', 'ExperimentID'});

% Initialize new columns for previous time steps
for lag = 1:num_previous
    for f = 1:length(base_features)
        new_col = sprintf('%s_prev%d', base_features{f}, lag);
        aggregated_features.(new_col) = NaN(height(aggregated_features), 1);
    end
end

% Add previous values using Experiment-aware lagging
experiment_ids = aggregated_features.ExperimentID;
for exp = unique(experiment_ids)'
    exp_mask = (experiment_ids == exp);
    exp_data = aggregated_features(exp_mask, :);
    
    % Shift data within each experiment
    for lag = 1:num_previous
        for f = 1:length(base_features)
            col_name = base_features{f};
            new_col = sprintf('%s_prev%d', col_name, lag);
            
            % Shift values down by 'lag' positions
            shifted_values = [NaN(lag,1); exp_data.(col_name)(1:end-lag)];
            aggregated_features.(new_col)(exp_mask) = shifted_values;
        end
    end
end

% Remove rows with NaN (first few rows of each experiment that can't get full history)
aggregated_features_enriched = rmmissing(aggregated_features);

% Verify the result
disp(['Original # rows: ' num2str(height(aggregated_features))]);
disp(['Enriched # rows: ' num2str(height(aggregated_features_enriched))]);
disp('New columns added:');
disp(aggregated_features_enriched.Properties.VariableNames(end-num_previous*length(base_features)+1:end));

