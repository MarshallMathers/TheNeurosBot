import numpy as np
import pandas as pd
import ta
from matplotlib import style
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score
from sklearn.metrics import confusion_matrix
from sklearn.externals import joblib
import seaborn as sns; sns.set()
import matplotlib.pyplot as plt
import functions
style.use("ggplot")

# This is so that when I print things to the console they display at the width of my monitor
console_width = 320
pd.set_option('display.width', console_width)
np.set_printoptions(linewidth=console_width)

"""
This makes use of the old data that we scrapped from exchanges, this file helped me build
    out the foundation for my SVM because it allowed me to play with smaller amounts of data
    cutting down on testing time.
"""

# Declares the file path
base = 'priceData/'
# What year does the function start to pull form
year = '2016'
# What is the pair the is being pulled
pair = 'BTC-USD'
# What is the starting month in the specified year
month = '2'
# How many months of data are being pulled in, in total
totalMonth = 26
# Stands for candle stick size, in this case I am pulling data in 5 minute intervals
csSize = 5

# Declares empty list to load all of the data into
tdata = [[], [], [], [], [], []]

# This is a for loop that loads in all of the data in the range and size specified above
for i in range(totalMonth):

    # Combines the variables stated above to make the path of the first file being read
    tmp = base + year + '/' + pair + month + 'min.data'
    currData = functions.aggregate(tmp, 1, csSize)

    print(tmp)

    for i in range(int(len(currData))):
        for j in range(6):
            tdata[j].append(currData[i][j])

    month = str(int(month) + 1)
    if int(month) > 12:
        month = str(int(month) - 12)
        year = str(int(year) + 1)

# Transposes the whole data set so that it's columns represent open, close, etc
train = np.array(tdata).T

# Because I am training my SVM to predict over an hour or so I make sure the whole data set
# is divisible by 12 so that all of my arrays are the same size when I got to split them up.
# Note: Pulling data in 5 minute chunks, so 5 * 12 = 1 Hour.
if len(train) % 12 != 0:
    chop = len(train) % 12
    train = train[:-chop]

# Split up the whole data set into the values we want to feed into our TA signals
train_open = pd.Series(train[:, 1])
train_high = pd.Series(train[:, 2])
train_low = pd.Series(train[:, 3])
train_close = pd.Series(train[:, 4])
train_volume = pd.Series(train[:, 5])


#########################################################
####               TA Signals                        ####
#########################################################

# Calculates a short and long Relative Strength Index
rsi_short = ta.momentum.rsi(train_close, n=9)
rsi_long = ta.momentum.rsi(train_close, n=14)

# Calculates a short and long True Strength Index
tsi_short = ta.momentum.tsi(train_close, r=14, s=9)
tsi_long = ta.momentum.tsi(train_close, r=25, s=13)

# Calculates a Money Flow index
mfi = ta.momentum.money_flow_index(train_high, train_low, train_close, train_volume, n=14)

# Calculates two Bollinger band indicators that return a 1 when crossed, otherwise return a 0
bband_high = ta.volatility.bollinger_hband_indicator(train_close, n=20)
bband_low = ta.volatility.bollinger_lband_indicator(train_close, n=20)


#########################################################
####                Data Handling                    ####
#########################################################

# Ensure all input array's are the same size
# The reason all arrays start from 48 is to ensure all TA signals have
# been calculated to avoid NAN or missing values
train_close = train_close[48:]
rsi_s = rsi_short[48:]
rsi_l = rsi_long[48:]
tsi_s = tsi_short[48:]
tsi_l = tsi_long[48:]
mfi = mfi[48:]
bband_high = bband_high[48:]
bband_low = bband_low[48:]

# Separate price to calculate the expected y values for training
price = functions.split(train_close)
price = np.stack((price[0], price[1], price[2], price[3], price[4], price[5],
                  price[6], price[7], price[8], price[9], price[10], price[11]), axis=-1)

# Generate the X data set for training the SVM, this data set splits the list of TA values into rows
# representing an hour to fit with the rest of the model, ensuring that values are accounted for.
X = functions.splitAndCompress_noPrice(rsi_s, tsi_s, rsi_l, tsi_l, mfi, bband_low, bband_high)

# Get the length of X to make y the same length
size = len(X)
# Create empty y training set. This will array will serve as both our training and testing data
y = np.zeros(size)

# Double check that both array's are the same size.
print("The shape of X:", X.shape)
print("The shape of y:", y.shape)


# Generate y data for training and testing
for i in range(1, size):

    # This stores the price from the beginning of the last hour
    currClose = price.item((i - 1, 0))
    # This takes the price at the beginning of the next hour
    futureClose = price.item((i, 0))
    # Calculates the difference to generate the appropriate signal
    diff = (futureClose - currClose) / currClose

    # Checks to see if the difference is greater than half a percentage
    # This generates a buy signal
    if diff > 0.005:
        y[i - 1] = 1

    # This generates a sell signal
    elif diff < -0.005:
        y[i - 1] = -1

    # This generates a do nothing signal
    # The reason this was included is because a lot of market movement is
    # un-tradable and I want my SVM to be able to recognize sideways movement
    else:
        y[i - 1] = 0


## Signal Processing
##############################################################
# This section of code is helpful for optimization and debugging

# generate empty lists to tally up how many of what kind of signals are generated
# each list is paired so that the values of X are stored with their corresponding y values
t_side_x = []
t_side_y = []
t_buy_x = []
t_buy_y = []
t_sell_x = []
t_sell_y = []

# Tallies up each signal
for i in range(len(X)):
    if y[i] == 0:
        t_side_x.append(X[i])
        t_side_y.append(0)
    elif y[i] == 1:
        t_buy_x.append(X[i])
        t_buy_y.append(1)
    else:
        t_sell_x.append(X[i])
        t_sell_y.append(-1)

# Converts them to np arrays
t_side_x = np.array(t_side_x)
t_side_y = np.array(t_side_y)
t_buy_x =  np.array(t_buy_x)
t_buy_y =  np.array(t_buy_y)
t_sell_x = np.array(t_sell_x)
t_sell_y = np.array(t_sell_y)

buys = len(t_buy_y)
sells = len(t_sell_y)
sideways = len(t_side_y)

# After storing how many buys, sells, and sideways movement signals they are returned to
# to represent the whole data set.
X = np.concatenate((t_side_x, t_buy_x, t_sell_x), axis=0)
y = np.concatenate((t_side_y, t_buy_y, t_sell_y), axis=0)

# Double check everything made it back into the arrays
print(X.shape)
print(y.shape)

# Print out how many of each signal was generated
print("Buys:", buys, "Sells:", sells, "Sideways:", sideways)

# Double check that no NAN values appeared or missing values
print(np.argwhere(np.isnan(X)))

# Shuffle everything so that we are ready to train!
X, y = functions.shuffleLists(X, y)

print(np.argwhere(np.isnan(X)))


#########################################################
####                 SVM Time                        ####
#########################################################

# Very basic way of splitting up the data into testing and training
train_X = X[:14000]
train_y = y[:14000]

test_X = X[14000:]
test_y = y[14000:]

# After a lot of messing around I settled on SGDClassifier
clf1 = SGDClassifier(loss='modified_huber', penalty='elasticnet', max_iter=1000, n_jobs=-1,
                     learning_rate='optimal', alpha=0.0001, class_weight={-1: .507, 0: 0.05, 1: 0.475})
clf1.fit(train_X, train_y)

results1_y = clf1.predict(test_X)

# Compare some of the signals generated
print(results1_y[:50])
print(test_y[:50])

# Run an accuracy test
acc1 = accuracy_score(test_y, results1_y)

# Print accuracy
print("Accuracy of model 1:", acc1)

# If the model is good, dump it to a file to use for trading
# joblib.dump(clf1, "SVM_Model.pkl")

# Generate a confustion Matrix to better understand what is being correctly classified and
# incorrectly classified
mat = confusion_matrix(test_y, results1_y)

# Print results to a graph
sns.heatmap(mat, square=True, annot=True, cbar=False) #, cmap='YlGnBu', flag, YlGnBu, jet
plt.xlabel('predicted value')
plt.ylabel('true value')

plt.show()

