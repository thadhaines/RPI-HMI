% RPI_HMI_log_grapher_003 - Deployable plotting code.

%%  Purpose: Read in log file, and plot data along time axis.
%   text scan will be used to read in column names
%   text scan will be used to read in timestamp and associated data
%   timestamp converted to time number via datenum
%   data will be plotted against time number via datetick
%   legend will be created from column names in csv file

%% Initialization
clear;clc;close all;

%% Load log
%fileID = fopen('2016.12.17_13.58.06_9_LED_prototype_01.csv');
%fileID = fopen('2016.12.17_14.52.07_9_LED_prototype_01.csv');

fileID = fopen('2016.12.18_01.15.41_9_LED_prototype_01.csv');
%fileID = fopen('2016.12.18_03.16.36_9_LED_prototype_01.csv');


fileID = fopen('2017.01.03_19.17.13_9_LED_prototype_02.csv');


%% Create cell of data column names
formatSpec = '%s'; N = 15;
C_text = textscan(fileID,formatSpec,N,'Delimiter',','); %collect column names

% Date[YYYY.MM.DD],Time[HH:MM:SS.ms],Log Number,FP101,FP102,FP103,FV201,FV202,FV203,FV204,EM201,EM202,Temp1,Temp2,pH
% create data cell, %f for later multiplication (graph scaling)
C_data0 = textscan(fileID,'%s %s %f %f %f %f %f %f %f %f %f %f %f %f %f','Delimiter',','); %matches format of data

%% Timestamp data -> datenumber for plotting on matlab formated axis
date = C_data0{1};
time = C_data0{2};
for ndx=1:length(C_data0{1})
    % create custom half second time vector (must know log interval)
    c_time(ndx) = .5 *(ndx-1);
end
dateTime = strcat(date, {','}, time);
date_format = 'yyyy.mm.dd,HH:MM:SS.FFF';
dateTimePlot = datenum(dateTime,date_format);%converts timestamp into time number

%% Plotting
figure
subplot(4,1,[1 2])

ndx = 4;    % begining of system status log values

while ndx <= N-3    % to create all plot as once
    plot(c_time,( C_data0{ndx}*.75 - (ndx-4) ),'linewidth',2)
    hold on
    ndx = ndx+ 1;
end

title(strvcat(['Log Starting at ',C_data0{2}{1},', On ', C_data0{1}{1}])) %format title from timestamp data
ylabel('Device Status')
xlabel('Time [seconds]')

legend(C_text{1}{4},C_text{1}{5},C_text{1}{6},...
    C_text{1}{7},C_text{1}{8},C_text{1}{9},...
    C_text{1}{10},C_text{1}{11},C_text{1}{12},'location','eastoutside') %creates legend from column names read in...
% setting x axis
x_lim = [0 c_time(end)];
xlim(x_lim)
set(gca,'XTick',(0:120:c_time(end)+60) )
set(gca,'YtickLabel',[' ']);
grid on

subplot(4,1,3)
%% temperature plots
plot(c_time,C_data0{13},'linewidth',2)
hold on
plot(c_time,C_data0{14},'linewidth',2)
y_max = max(max(C_data0{13}),max(C_data0{14}));
y_min = min(min(C_data0{13}),min(C_data0{14}));
y_span = round(y_max-y_min)/2;
ylim(round([y_min-y_span y_max+y_span]))

legend(C_text{1}{13},C_text{1}{14},'location','eastoutside')
ylabel('^oC')
xlabel('Time [seconds]')
set(gca,'XTick',(0:120:c_time(end)+60) )
xlim(x_lim)
grid on

%% pH plot
subplot(4,1,4)
plot(c_time,C_data0{15},'linewidth',2)
ylim([0 14])
xlabel('Time [seconds]')
ylabel('pH')
y_max = max(C_data0{15});
y_min = min(C_data0{15});
y_span = round(y_max-y_min)/2;
ylim(round([y_min-y_span y_max+y_span]))

legend( horzcat( C_text{1}{15},'usb'),'location','eastoutside')
set(gca,'XTick',(0:120:c_time(end)+60) )
xlim(x_lim)
grid on