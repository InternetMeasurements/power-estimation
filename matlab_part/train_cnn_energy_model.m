%% Load Data
load(fullfile('results', 'aggregated_features.mat'));  % Loads aggregated_features

%% Choose target variable (Log transformed or not)
use_log_target = false;
if use_log_target
    target = aggregated_features.LogMeanPower;
else
    target = aggregated_features.MeanPower;
end

%% Prepare Input Features and Target
input_features = aggregated_features{:, {'TXBytes', 'RXBytes', 'MeanIAT', 'TXRatio'}};
target = aggregated_features.MeanPower; % or LogMeanPower

% Normalize features
[input_features_norm, mu, sigma] = zscore(input_features);

% Hyperparameters
sequence_length = 10;  % Number of timesteps in each sequence
num_features = size(input_features, 2);

% Create sequences
num_sequences = size(input_features_norm, 1) - sequence_length;
X = cell(num_sequences, 1);
Y = zeros(num_sequences, 1);

for i = 1:num_sequences
    % Extract sequence and store as a [features × timesteps] matrix
    X{i} = input_features_norm(i:i+sequence_length-1, :)';  % Transpose to [features × timesteps]
    
    % Target is the power value at the END of the sequence
    Y(i) = target(i + sequence_length - 1);
end

% Split into training and validation (80-20 split)
cv = cvpartition(num_sequences, 'HoldOut', 0.2);
XTrain = X(training(cv),:,:);
YTrain = Y(training(cv));
XVal = X(test(cv),:,:);
YVal = Y(test(cv));

%% Define CNN Model
layers = [
    sequenceInputLayer(num_features) % 4 input features
    
    convolution1dLayer(3, 32, 'Padding', 'same')
    batchNormalizationLayer
    sigmoidLayer % Replaced ReLU with Sigmoid
    
    convolution1dLayer(3, 64, 'Padding', 'same')
    batchNormalizationLayer
    sigmoidLayer % Replaced ReLU with Sigmoid
    
    globalAveragePooling1dLayer
    
    fullyConnectedLayer(32)
    sigmoidLayer % Replaced ReLU with Sigmoid
    
    fullyConnectedLayer(1)
    regressionLayer
];

%% Training Options
options = trainingOptions('adam', ...
    'MaxEpochs', 30, ...
    'MiniBatchSize', 64, ...
    'InitialLearnRate', 1e-3, ...
    'Shuffle', 'every-epoch', ...
    'ValidationData', {XVal, YVal}, ...
    'ValidationFrequency', 20, ...
    'Plots', 'training-progress', ...
    'Verbose', true);

%% Train the Model
net = trainNetwork(XTrain, YTrain, layers, options);

%% Save Model and Normalization Info
save('results/trained_cnn_model.mat', 'net', 'mu', 'sigma', 'sequence_length', 'use_log_target');
%% Use the trained network to make predictions
YPred = predict(net, XVal);

% If you used log transformation, convert back to original scale
if use_log_target
    YPred = exp(YPred);
    YVal_original = exp(YVal);
else
    YVal_original = YVal;
end
%% Scatter Plot
figure;
scatter(YVal_original, YPred, 20, 'filled');
hold on;
plot([min(YVal_original), max(YVal_original)], [min(YVal_original), max(YVal_original)], 'k--');  % Perfect fit line
hold off;
xlabel('Actual Power (W)');
ylabel('Predicted Power (W)');
title('Predicted vs. Actual Power');
axis equal;
grid on;