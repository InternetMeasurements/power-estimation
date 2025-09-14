%% --- Step 1: Temporarily remove target & ID columns ---
exclude_vars = {'MeanPower', 'LogMeanPower', 'ExperimentID'};
feature_vars = setdiff(aggregated_features_enriched.Properties.VariableNames, exclude_vars);
X = aggregated_features_enriched(:, feature_vars);

%% --- Step 2: Compute correlation matrix ---
corr_matrix = corr(X{:,:}, 'Rows', 'complete');

% Find and remove highly correlated features (≥90%)
high_corr_threshold = 0.90;
to_remove = false(1, width(X));

for i = 1:width(X)
    for j = (i+1):width(X)
        if abs(corr_matrix(i,j)) >= high_corr_threshold
            to_remove(j) = true; % Remove the later one
        end
    end
end

% Get names of retained features
reduced_features = X.Properties.VariableNames(~to_remove);

disp(['Removed ', num2str(sum(to_remove)), ' highly correlated features:']);
disp(X.Properties.VariableNames(to_remove)');

%% --- Step 3: Add back target and ID columns ---
final_vars = [reduced_features, {'MeanPower', 'ExperimentID'}];
aggregated_features_reduced = aggregated_features_enriched(:, final_vars);

%% --- Step 4: Verify result ---
disp('Reduced feature table:');
disp(head(aggregated_features_reduced));
disp(['Final feature count (excluding target/ID): ', ...
    num2str(width(aggregated_features_reduced)-3)]);  % Minus MeanPower, LogMeanPower, ExperimentID

%% --- Step 5: Visualize correlation before/after ---
figure;
subplot(1,2,1);
imagesc(abs(corr_matrix)); colorbar; title('Original Correlations');

subplot(1,2,2);
new_corr = corr(aggregated_features_reduced{:, reduced_features}, 'Rows', 'complete');
imagesc(abs(new_corr)); colorbar; title('After Removal');