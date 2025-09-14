% Define paths
data_dir = 'data/grouped_experiments';
experiments = dir(data_dir);
experiments = experiments([experiments.isdir] & ~startsWith({experiments.name}, '.')); % Filter folders only
num_experiments = length(experiments);

% Preallocate output
all_features = cell(num_experiments, 1);
experiment_settings = cell(num_experiments, 1); % Store experiment metadata

for i = 1:num_experiments
    fprintf('Processing experiment %d/%d...\n', i, num_experiments);
       
    % --- Load and Trim GPI-based Power Trace ---
    gpi_file = fullfile(data_dir, experiments(i).name, 'gpi_trace.csv');
    gpi_data = readtable(gpi_file); % Columns: Timestamp, Value
    
    % Find first two rising edges (Value == 1)
    rising_edges = gpi_data.Timestamp(gpi_data.Value == 1);
    if length(rising_edges) < 2
        error('Expected at least two rising edges in GPI trace');
    end
    start_time = rising_edges(1);
    end_time   = rising_edges(2);
    
    % Load full power trace
    power_file = fullfile(data_dir, experiments(i).name, 'power_trace.csv');
    power_data = readtable(power_file);
    
    % Trim power trace to [start_time, end_time]
    in_range = power_data.Timestamp >= start_time & power_data.Timestamp <= end_time;
    power_data = power_data(in_range, :);
    
    % Shift timestamps so they start from 0
    power_data.Timestamp = power_data.Timestamp - start_time;
    
    % Extract trimmed power trace
    power_timestamps = power_data.Timestamp;   % Seconds
    power_values = power_data.Value;           % Watts (Instantaneous Power)

    % --- Load eBPF Network Data ---
    ebpf_file = fullfile(data_dir, experiments(i).name, 'ebpf_trace.csv');
    ebpf_data = readtable(ebpf_file);
    ebpf_timestamps_ns = ebpf_data.Timestamp_ns_; % Nanoseconds
    packet_lengths = ebpf_data.PacketLength;
    iat_ns = ebpf_data.IAT_ns_;                % IAT in nanoseconds
    iat = iat_ns / 1e9;                        % Convert IAT to seconds
    direction = ebpf_data.Direction;
    
    % --- ALIGN TIMESTAMPS (eBPF) ---
    ebpf_start_ns = ebpf_timestamps_ns(1);
    ebpf_timestamps_relative = (double(ebpf_timestamps_ns) / 1e9) - (double(ebpf_start_ns) / 1e9);
    last_ebpf_time = max(ebpf_timestamps_relative);
    
    % --- BIN DATA (0.5sec bins) ---
    bin_size = 0.5; 
    last_edge = ceil(last_ebpf_time / bin_size) * bin_size;
    bin_edges = 0:bin_size:last_edge;
    num_bins = length(bin_edges) - 1;
    
    % Bin network metrics from eBPF
    [~, ~, bin_idx_ebpf] = histcounts(ebpf_timestamps_relative, bin_edges);
    
    % Calculate TX and RX bytes
    tx_bytes = accumarray(bin_idx_ebpf, packet_lengths .* (direction == "Outgoing"), [num_bins, 1], @sum);
    rx_bytes = accumarray(bin_idx_ebpf, packet_lengths .* (direction == "Incoming"), [num_bins, 1], @sum);
    
    % --- Calculate basic metrics ---
    mean_iat = accumarray(bin_idx_ebpf, iat, [num_bins, 1], @mean);
    tx_ratio = accumarray(bin_idx_ebpf, (direction == "Outgoing"), [num_bins, 1], @mean);
    std_iat = accumarray(bin_idx_ebpf, iat, [num_bins, 1], @std);           % Jitter
    max_iat = accumarray(bin_idx_ebpf, iat, [num_bins, 1], @max);           % Max gap
    min_iat = accumarray(bin_idx_ebpf, iat, [num_bins, 1], @min);           % Min gap
    burstiness_iat = std_iat ./ mean_iat;                                   % Burstiness metric
    burstiness_iat(mean_iat == 0) = 0;
    packet_count = accumarray(bin_idx_ebpf, ones(size(iat)), [num_bins, 1], @sum); % Total packet count
    packet_rate = packet_count / bin_size;                                   % Packets per second
    
    % --- Packet length stats ---
    std_packet_length = accumarray(bin_idx_ebpf, packet_lengths, [num_bins, 1], @std);
    max_packet_length = accumarray(bin_idx_ebpf, packet_lengths, [num_bins, 1], @max);
    mean_packet_length = accumarray(bin_idx_ebpf, packet_lengths, [num_bins, 1], @mean);
    
    % Skewness and kurtosis require grouped computations
    skew_packet_length = accumarray(bin_idx_ebpf, packet_lengths, [num_bins, 1], ...
        @(x) skewness(double(x)));
    kurt_packet_length = accumarray(bin_idx_ebpf, packet_lengths, [num_bins, 1], ...
        @(x) kurtosis(double(x)));
    
    % --- Direction-based counts ---
    count_tx = accumarray(bin_idx_ebpf, direction == "Outgoing", [num_bins, 1], @sum);
    count_rx = accumarray(bin_idx_ebpf, direction == "Incoming", [num_bins, 1], @sum);
    tx_rx_ratio = count_tx ./ max(count_rx, 1);  % Avoid division by zero
    total_packet_count = count_tx + count_rx;

    
    % --- BIN POWER VALUES ---
    [~, ~, bin_idx_power] = histcounts(power_timestamps, bin_edges);
    valid_idx = bin_idx_power > 0;
    mean_power = accumarray(bin_idx_power(valid_idx), power_values(valid_idx), [num_bins, 1], @mean, NaN);

    
    % --- STORE FEATURES ---
    % All variables are length num_bins, ensure consistent truncation
    min_len = num_bins;
features = table(...
    tx_bytes(1:min_len), ...
    rx_bytes(1:min_len), ...
    mean_iat(1:min_len), ...
    std_iat(1:min_len), ...
    max_iat(1:min_len), ...
    min_iat(1:min_len), ...
    burstiness_iat(1:min_len), ...
    packet_rate(1:min_len), ...
    tx_ratio(1:min_len), ...
    count_tx(1:min_len), ...
    count_rx(1:min_len), ...
    tx_rx_ratio(1:min_len), ...
    total_packet_count(1:min_len), ...
    std_packet_length(1:min_len), ...
    max_packet_length(1:min_len), ...
    mean_packet_length(1:min_len), ...
    skew_packet_length(1:min_len), ...
    kurt_packet_length(1:min_len), ...
    mean_power(1:min_len), ...
    'VariableNames', {...
        'TXBytes', 'RXBytes', ...
        'MeanIAT', 'StdIAT', 'MaxIAT', 'MinIAT', 'BurstinessIAT', 'PacketRate', ...
        'TXRatio', 'CountTX', 'CountRX', 'TX_RX_Ratio', 'TotalPacketCount', ...
        'StdPacketLength', 'MaxPacketLength', 'MeanPacketLength', ...
        'SkewPacketLength', 'KurtosisPacketLength', ...
        'MeanPower'});

    % Add experiment ID and settings
    features.ExperimentID = repmat(i, height(features), 1);
    all_features{i} = features;
    experiment_settings{i} = experiments(i).name;
end

% Combine all experiments into one table
aggregated_features = vertcat(all_features{:});
%% Remove Rows with Any NaNs
aggregated_features = rmmissing(aggregated_features);
save(fullfile('results', 'aggregated_features.mat'), 'aggregated_features', 'experiment_settings');
%% Check Data Distrubtion
figure;  
histogram(aggregated_features.MeanPower);  
xlabel('Power (W)');  
ylabel('Frequency');  
title('Distribution of Target Variable (Power)');


