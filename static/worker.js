self.onmessage = function (event) {
    const { jobId, xkf1Data, imuData, RCOUData, ranges, unselectedAlpha } = event.data;

    // ranges is an array of { start, end } in milliseconds.
    // A sample is selected if it falls inside ANY range.
    const isSelected = (unixSeconds) => {
        const t = unixSeconds * 1000;
        return ranges.some((r) => t >= r.start && t <= r.end);
    };

    // Gradient for xkf1Data
    const xkf1Colors = xkf1Data.map((item, index, array) => {
        const gradientColor = `rgb(${Math.floor(255 * index / array.length)}, 0, ${Math.floor(255 - 255 * index / array.length)})`;
        return isSelected(item.Unix_Epoch_Time) ? gradientColor : `rgba(24, 24, 24, ${unselectedAlpha})`;
    });

    // Prepare color data for IMU charts
    const createImuColors = (color) => imuData.map((item) =>
        isSelected(item.Unix_Epoch_Time) ? color : `rgba(48, 48, 48, ${unselectedAlpha})`
    );

    // Prepare color data for RCOU charts
    const createRCOUColors = (color) => RCOUData.map((item) =>
        isSelected(item.Unix_Epoch_Time) ? color : `rgba(48, 48, 48, ${unselectedAlpha})`
    );

    self.postMessage({
        jobId,
        xkf1Colors,
        imuAccXColors: createImuColors('rgb(255, 0, 0)'),   // Red
        imuAccYColors: createImuColors('rgb(0, 255, 0)'),   // Green
        imuAccZColors: createImuColors('rgb(0, 0, 255)'),   // Blue
        RCOUColors: createRCOUColors('rgb(255,165,0)'),     // Orange
    });
};