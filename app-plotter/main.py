# Global Imports
import pandas as pd

from bokeh.layouts import row, layout
from bokeh.models import ColumnDataSource, Select, Range1d
from bokeh.plotting import curdoc, figure
from bokeh.models import CustomJS, DatetimeTickFormatter

# In minutes
BAR_PERIOD = 5

# Percent of the width.
BAR_PADDING = 20

# Bar width.
# 1 sec = 1000 milliseconds, 1 min = 60 seconds
BAR_WIDTH = (BAR_PERIOD * 60 * 1000) - ((BAR_PERIOD * 60 * 1000) * ((BAR_PADDING / 100) * 2))

# Bokeh canvas width.
PLOT_WIDTH = 900

SMA, EMA = 'SMA (13/30)', 'EMA (13/30)'

# Data Container
source = ColumnDataSource(dict(
    index=[],
    time=[],
    low=[],
    high=[],
    open=[],
    close=[],
    candle_bound_min=[],
    candle_bound_max=[],
    ma_slow=[],
    ma_fast=[],
    macdh=[],
    macd_bound_min=[],
    macd_bound_max=[]
))

# Configure PLOT_1
p1 = figure(plot_width=PLOT_WIDTH,
            plot_height=600,
            tools="xpan,xwheel_zoom,reset,save",
            active_drag='xpan',
            active_scroll='xwheel_zoom',
            x_axis_type='datetime',
            sizing_mode='stretch_width',
            y_axis_location="right")

# MA Slow
p1.line(x='time', y='ma_slow', color='#6cbf40', source=source)

# MA Fast
p1.line(x='time', y='ma_fast', color='#5740bf', source=source)

# Plot Candlesticks (bokeh-candlestick)
p1.segment(x0='time', y0='high', x1='time', y1='low', source=source, color='#545454')
p1.vbar(x='time', width=BAR_WIDTH, top='open', bottom='close', source=source,
        fill_color='#545454', line_color='#959595', line_width=0.1)

p1.xaxis.formatter = DatetimeTickFormatter(
    days=["%m/%d %H:%M"],
    months=["%m/%d %H:%M"],
    hours=["%m/%d %H:%M"],
    minutes=["%m/%d %H:%M"]
)


# Configure PLOT_2
p2 = figure(plot_width=PLOT_WIDTH,
            plot_height=200,
            x_range=p1.x_range,
            tools='xpan,xwheel_zoom,xbox_zoom,reset',
            active_drag='xpan',
            active_scroll='xwheel_zoom',
            x_axis_type='datetime',
            sizing_mode='stretch_width',
            y_axis_location='right')

# MACD Histogram: macdh
p2.vbar(x='time', bottom=0, top='macdh', width=BAR_WIDTH, fill_color='#000000', alpha=1, source=source)

p2.xaxis.formatter = DatetimeTickFormatter(
    days=["%m/%d %H:%M"],
    months=["%m/%d %H:%M"],
    hours=["%m/%d %H:%M"],
    minutes=["%m/%d %H:%M"]
)

p2.y_range = Range1d(-10, 10)


def _get_OHLCV_data():
    # Data Import
    df = pd.read_csv('./app-plotter/data/data.csv')

    df['time'] = pd.to_datetime(df['timestamp'], unit='s')
    df.rename(columns={'time': 'date'}, inplace=True)

    pair_df = df.loc[df.pair == 'BTC/EUR'].copy()
    pair_df.drop(['timestamp', 'pair', 'volume'], axis=1, inplace=True)

    cols = list(pair_df)
    cols.insert(0, cols.pop(cols.index('date')))

    df["date"] = pd.to_datetime(df["date"], format='%Y-%m-%d %H:%M:%S', utc=True)  # Adjust this
    pair_df = pair_df.loc[:, cols]

    # Last row contains data from the current 5min. We should not be using the data from the last
    # row since the candle has not closed yet, and the values are likely to keep changing.
    pair_df = pair_df[:-1]

    return pair_df


def update():
    local_df = _get_OHLCV_data()

    # Time Zone
    local_df['date'] = local_df['date'].dt.tz_localize("UTC").dt.tz_convert('Europe/London').dt.tz_localize(None)

    if mavg.value == SMA:
        # Calculate the Simple Moving Average slots.
        ma_slow = local_df['close'].copy().rolling(30).mean()
        ma_fast = local_df['close'].copy().rolling(13).mean()

    if mavg.value == EMA:
        # Calculate the Exponential Moving Average slots.
        ma_slow = local_df['close'].ewm(span=30, adjust=False).mean()
        ma_fast = local_df['close'].ewm(span=13, adjust=False).mean()

    # Add to data-frame.
    local_df['ma_slow'] = ma_slow
    local_df['ma_fast'] = ma_fast

    # Add OHLC bounds
    # These bounds are used to re-fit the y-scale so that all candlesticks are visible within in the current window.
    local_df['candle_bound_min'] = local_df['low']
    local_df['candle_bound_max'] = local_df['high']

    # Calculate and store MACD series.
    macd_fast_ma = local_df['close'].ewm(span=13, adjust=False).mean()
    macd_slow_ma = local_df['close'].ewm(span=30, adjust=False).mean()
    macd = macd_fast_ma - macd_slow_ma

    # Calculate and store MACD signal and histogram series.
    macd_df = pd.DataFrame()
    macd_df['macd'] = macd
    macd_df['signal'] = macd_df['macd'].ewm(span=9, adjust=False).mean()
    macd_df['histogram'] = macd_df['macd'] - macd_df['signal']

    # Calculate and store MACD bounds.
    macd_df['bound_min'] = macd_df.min(axis=1)
    macd_df['bound_max'] = macd_df.max(axis=1)

    # Get MACD into the main dataframe.
    local_df['macdh'] = macd_df['histogram']
    local_df['macd_bound_min'] = macd_df['bound_min']
    local_df['macd_bound_max'] = macd_df['bound_max']

    # Create a new data-container.
    new_data = dict(
        index=local_df.index,
        time=local_df.date,
        open=local_df.open,
        high=local_df.high,
        low=local_df.low,
        close=local_df.close,
        candle_bound_min=local_df.candle_bound_min,
        candle_bound_max=local_df.candle_bound_max,
        ma_slow=local_df.ma_slow,
        ma_fast=local_df.ma_fast,
        macdh=local_df.macdh,
        macd_bound_min=local_df.macd_bound_min,
        macd_bound_max=local_df.macd_bound_max
    )

    # Swap the current data with the new data.
    source.data = new_data


# The callback used to update the y-range on the top plot based on the min/max bounds of the currently
# visible data. This provides optimum canvas usage where we have the lowest value at the bottom of the
# chart and the highest value at the top.


callback_top = CustomJS(args={'y_range': p1.y_range, 'source': source}, code='''
    clearTimeout(window._autoscale_timeout_top_plot);

    var index = source.data.time,
        low = source.data.candle_bound_min,
        high = source.data.candle_bound_max,
        start = cb_obj.start,
        end = cb_obj.end,
        min = Infinity,
        max = -Infinity;

    for (var i=0; i < index.length; ++i) {
        if (start <= index[i] && index[i] <= end) {
            max = Math.max(high[i], max);
            min = Math.min(low[i], min);
        }
    }

    console.log(`[top_plot] start: ${start}, end: ${end}`);
    console.log(`[top_plot] min: ${min}, max: ${max}`);

    var pad = (max - min) * .05;

    window._autoscale_timeout_top_plot = setTimeout(function() {
        y_range.start = min - pad;
        y_range.end = max + pad;
    });
''')


# The callback used to update the y-range on the bottom plot based on the min/max bounds of the currently
# visible data.


callback_bottom = CustomJS(args={'y_range': p2.y_range, 'source': source}, code='''
    clearTimeout(window._autoscale_timeout_bottom_plot);

    var index = source.data.time,
        low = source.data.macd_bound_min,
        high = source.data.macd_bound_max,
        start = cb_obj.start,
        end = cb_obj.end,
        min = Infinity,
        max = -Infinity;

    for (var i=0; i < index.length; ++i) {
        if (start <= index[i] && index[i] <= end) {
            max = Math.max(high[i], max);
            min = Math.min(low[i], min);
        }
    }

    console.log(`[bottom_plot] start: ${start}, end: ${end}`);
    console.log(`[bottom_plot] min: ${min}, max: ${max}`);

    var pad = (max - min) * .05;

    window._autoscale_timeout_bottom_plot = setTimeout(function() {
        y_range.start = min - pad;
        y_range.end = max + pad;
    });
''')


mavg = Select(title='Moving Average', value=SMA, options=[SMA, EMA])

p1.x_range.js_on_change('start', callback_top)
p2.x_range.js_on_change('start', callback_bottom)

mavg.on_change('value', lambda attr, old, new: update())

inputs = row([mavg], width=130, height=60)
inputs.sizing_mode = "fixed"

dashboard_layput = layout([
    [inputs],
    [p1],
    [p2],
], sizing_mode='stretch_width')

# Initial update.
update()

curdoc().add_root(dashboard_layput)
curdoc().title = "OHLC - Minimal"

# vim: ts=4 ft=python nowrap fdm=marker
