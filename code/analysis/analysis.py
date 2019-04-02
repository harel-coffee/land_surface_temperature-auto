'''
Here are a collection of functions for analyzing the land surface temperature and
thermal radiance from LandSat images of cities
'''

# import libraries
import matplotlib as mpl
mpl.use('Agg')
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import brewer2mpl
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn import preprocessing
import pickle
import code
from joblib import Parallel, delayed
pd.options.mode.chained_assignment = 'raise'
import itertools

# regression libraries
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.ensemble.partial_dependence import partial_dependence
from sklearn.metrics import mean_squared_error, r2_score
from pyearth import Earth
from pygam import LinearGAM

# init logging
import sys
# sys.path.append("code")
# from logger_config import *
# logger = logging.getLogger(__name__)


RANDOM_SEED = 3201

def main():
    '''
    '''
    # loop cities and all
    cities = ['bal', 'por', 'det', 'phx']
    # import data
    df = import_data(cities, grid_size)

    # present the data - density plot
    # plot_density(df, cities)

    # regression
    ## train on three cities, test on one
    loss = regression_cityholdouts(df, cities)
    # plot the points
    plot_holdout_points(loss)

    ## for each city, train and test
    sim_num = 50 # number of holdouts
    regressions(df, cities, sim_num)
    plot_holdouts()

    # variable importance and partial dependence
    # reg_gbm = full_gbm_regression(df, cities)

    # variable selection
    loop_variable_selection(df, cities)

    # based on the results of the variable selection, rerun the regression and
    # create the variable importance plots
    #vars_selected = ['tree_mean', 'ndvi_mean_mean', 'alb_mean_mean', 'elev_min_sl', 'elev_max', 'tree_max_sl']
    # vars_selected = ['tree_mean', 'ndvi_mean_mean', 'alb_mean_mean', 'alb_mean_min', 'elev_min_sl', 'ndvi_mean_min']
    # vars_selected = ['tree_mean', 'ndvi_mean_mean', 'alb_mean_mean', 'elev_min', 'alb_mean_min_sl', 'elev_max']
    # reg_gbm, X_train = full_gbm_regression(df, cities, vars_selected)
    # #
    # # # plot the variable importance
    # importance_order = plot_importance(reg_gbm, cities)
    # #
    # # # plot the partial dependence
    # plot_dependence(importance_order, reg_gbm, cities, X_train, vars_selected, show_plot=False)

def import_data(grid_size, selected_vars = True):
    if selected_vars:
        df = pd.read_csv('data/data_vif_{}.csv'.format(grid_size))
        df = df.drop('Unnamed: 0', axis=1)
    else:
        df = pd.read_csv('data/data_regressions_{}_20190324.csv'.format(grid_size))
        df = df.drop('Unnamed: 0', axis=1)
    return(df)


def regressions(df, cities, sim_num, grid_size, do_par = False):
    '''
    to compare regression out-of-bag accuracy I need to split into test and train
    I also want to scale some of the variables
    '''
    # for city in cities:
    df_city = df#[df['city']==city] #df_city = df.loc[df['city']==city]
    predict_quant = 'lst'
    df_city, response = prepare_lst_prediction(df_city)
    # conduct the holdout
    if do_par:
        CORES_NUM = min(50,int(os.cpu_count()))
        Parallel(n_jobs=CORES_NUM)(delayed(single_regression)(df_city, response, grid_size, predict_quant, i) for i in range(sim_num))
    else:
        for i in range(sim_num):
            single_regression(df_city, response, grid_size, predict_quant, i)


def single_regression(df_city, response, grid_size, predict_quant, i):
    '''
    fit the different models for a single holdout
    '''
    city = str(i)
    # prepare the results of the holdout
    loss = pd.DataFrame()
    # divide into test and training sets
    X_train, X_test, y_train, y_test = split_holdout(df_city, response, test_size=0.20)#, random_state=RANDOM_SEED)
    # drop unnecessary variables
    X_train, X_test = subset_regression_data(X_train, X_test)
    # response values
    y = define_response_lst(y_train, y_test)
    # null model
    loss = regression_null(y, city, predict_quant, loss)
    # GradientBoostingRegressor
    loss = regression_gradientboost(X_train, y, X_test, city, predict_quant, loss)
    # multiple linear regression
    loss = regression_linear(X_train, y, X_test, city, predict_quant, loss)
    # random forest regression
    loss = regression_randomforest(X_train, y, X_test, city, predict_quant, loss)
    # mars
    loss = regression_mars(X_train, y, X_test, city, predict_quant, loss)
    # gam
    loss = regression_gam(X_train, y, X_test, city, predict_quant, loss)
    # save results
    loss.to_csv('data/regression/holdout/holdout{}_results_{}.csv'.format(i, grid_size))


def regression_cityholdouts(df, cities):
    '''
    to compare regression out-of-bag accuracy I need to split into test and train
    I also want to scale some of the variables
    '''
    predict_quant = 'lst'

    # prep y
    df, response = prepare_lst_prediction(df)
    loss = pd.DataFrame()
    for city in cities:
        train_idx = np.where(df['city'] != city)
        test_idx = np.where(df['city'] == city)
        # divide into test and training sets
        X_train = df.iloc[train_idx].copy()
        y_train = response.iloc[train_idx].copy()
        X_test = df.iloc[test_idx].copy()
        y_test = response.iloc[test_idx].copy()
        # drop unnecessary variables
        X_train, X_test = subset_regression_data(X_train, X_test)
        # response values
        y = define_response_lst(y_train, y_test)
        ### do the holdouts
        city = 'hold-{}'.format(city)
        # null model
        loss = regression_null(y, city, predict_quant, loss)
        # GradientBoostingRegressor
        loss = regression_gradientboost(X_train, y, X_test, city, predict_quant, loss)
        # multiple linear regression
        loss = regression_linear(X_train, y, X_test, city, predict_quant, loss)
        # random forest regression
        loss = regression_randomforest(X_train, y, X_test, city, predict_quant, loss)
        # mars
        loss = regression_mars(X_train, y, X_test, city, predict_quant, loss)
        # gam
        loss = regression_gam(X_train, y, X_test, city, predict_quant, loss)
    return(loss)


def prepare_lst_prediction(df):
    '''
    to predict for thermal radiance, let's remove land surface temp and superfluous
    thermal radiance values
    '''
    # drop lst
    lst_vars = ['lst_day_mean','lst_night_mean']
    lst_mean = df[lst_vars].copy()
    df = df.drop(lst_vars, axis=1)

    return(df, lst_mean)


def subset_regression_data(X_train, X_test):
    '''
    drop unnecessary variables
    '''
    vars_all = X_train.columns.values
    cities = np.unique(X_train['city'])

    # drop the following variables
    vars_drop = ['city','holdout','x','y']
    X_train = X_train.drop(vars_drop, axis=1)
    X_test = X_test.drop(vars_drop, axis=1)

    return(X_train, X_test)


def define_response_lst(y_train, y_test):
    y = {}
    y['day_train'] = y_train['lst_day_mean']
    y['night_train'] = y_train['lst_night_mean']
    # test
    y['day_test'] = y_test['lst_day_mean']
    y['night_test'] = y_test['lst_night_mean']
    return(y)


def calculate_partial_dependence(df, grid_size, boot_index = None):
    '''
    fit the models to the entire dataset
    loop through each feature
    vary the feature over its range
    predict the target variable to see how it is influenced by the feature
    '''
    results_partial = pd.DataFrame()
    df, target = prepare_lst_prediction(df)
    df  = subset_regression_data(df, df)[0]
    df_reference = df.copy()
    feature_resolution = 25
    # loop day and night
    for h in ['lst_day_mean', 'lst_night_mean']:
        print(h)
        ###
        # fit models
        ###
        # gradient boosted tree
        gbm = GradientBoostingRegressor(max_depth=2, random_state=RANDOM_SEED, learning_rate=0.1, n_estimators=500, loss='ls')
        gbm.fit(df, target[h])
        # random forest
        rf = RandomForestRegressor(random_state=RANDOM_SEED, n_estimators=500, max_features=1/3)
        rf.fit(df, target[h])
        # mars
        mars = Earth(max_degree=1, penalty=1.0, endspan=5)
        mars.fit(df, target[h])
        # GAM
        gam = LinearGAM(n_splines=10).fit(df, target[h])
        # linear
        mlr = LinearRegression()
        mlr = mlr.fit(df, target[h])
        ###
        # loop through features and their ranges
        ###
        for var_interest in ['alb_mean','bldg','tree_mean']:#list(df): #['tree_mean','density_housesarea']:
            # loop through range of var_interest
            var_values = np.linspace(np.percentile(df[var_interest],1),np.percentile(df[var_interest],99), feature_resolution)
            df_change = df.copy()
            for x in var_values:
                df_change[var_interest] = x
                # gbm
                pred = gbm.predict(df_change)
                # save results
                results_partial = results_partial.append({'model': 'gbrt', 'dependent':h,'independent':var_interest,
                                                          'x':x, 'mean':np.mean(pred), 'boot': boot_index}, ignore_index=True)
                # rf
                pred = rf.predict(df_change)
                # save results
                results_partial = results_partial.append({'model': 'rf', 'dependent':h,'independent':var_interest,
                                                          'x':x, 'mean':np.mean(pred), 'boot': boot_index}, ignore_index=True)
                # mars
                pred = mars.predict(df_change)
                # save results
                results_partial = results_partial.append({'model': 'mars', 'dependent':h,'independent':var_interest,
                                                          'x':x, 'mean':np.mean(pred), 'boot': boot_index}, ignore_index=True)
                # gam
                pred = gam.predict(df_change)
                # save results
                results_partial = results_partial.append({'model': 'gam', 'dependent':h,'independent':var_interest,
                                                          'x':x, 'mean':np.mean(pred), 'boot': boot_index}, ignore_index=True)
                # mlr
                pred = mlr.predict(df_change)
                # save results
                results_partial = results_partial.append({'model': 'mlr', 'dependent':h,'independent':var_interest,
                                                          'x':x, 'mean':np.mean(pred), 'boot': boot_index}, ignore_index=True)
            # save results
            if boot_index:
                results_partial.to_csv('data/regression/bootstrap_{}/results_partial_dependence_{}.csv'.format(grid_size,boot_index))
            else:
                results_partial.to_csv('data/regression/results_partial_dependence_{}.csv'.format(grid_size))

def calc_swing(results_pd, grid_size):
    '''
    calculate the variable importance (swing)
    input: the results of the partial dependence
    now calculate the maximum change of the target for each feature
    the result is the swing, a measure of variable importance
    '''
    features = np.unique(results_pd['independent'])
    targets = np.unique(results_pd['dependent'])
    models = np.unique(results_pd['model'])
    # init df
    results_swing = pd.DataFrame()
    # loop targets
    for h in targets:
        # loop models
        for m in models:
            # calculate the range of the target for each feature
            model_range = results_pd.loc[(results_pd['dependent']==h) & (results_pd['model']==m)].groupby(['independent']).agg(np.ptp)
            # calc sum of range
            range_sum = model_range['mean'].sum()
            # calc swing
            swing = model_range['mean']/range_sum
            # put into dataframe
            swing = swing.to_frame('swing').reset_index()
            swing['model'] = m
            swing['dependent'] = h
            # save
            results_swing = results_swing.append(swing, ignore_index=True)
        # save results
        results_swing.to_csv('data/regression/results_swing_{}.csv'.format(grid_size))

def bootstrap_main(df, grid_size, boot_num, do_par = False):
    '''
    loop the bootstraps to calculate the partial_dependence
    '''
    if do_par:
        CORES_NUM = min(50,int(os.cpu_count())-4)
        Parallel(n_jobs=CORES_NUM)(delayed(boot_pd)(df, grid_size, boot_index) for boot_index in range(boot_num))
    else:
        for boot_index in range(boot_num):
            boot_pd(df, grid_size, boot_index)

def boot_pd(df, grid_size, boot_index):
    '''
    sample the holdout numbers with replacement to create bootstrapped df
    fit the models and calculate the partial dependence
    '''
    # resample the holdout numbers
    holdout_numbers = np.unique(df.holdout)
    holdout_sample = np.random.choice(holdout_numbers, len(holdout_numbers), replace=True)
    # create the df based on this sample
    sample_index = [list(df[df.holdout == x].index) for x in holdout_sample]
    sample_index = list(itertools.chain.from_iterable(sample_index))
    df = df.loc[sample_index]
    # calculate the pd
    calculate_partial_dependence(df, grid_size, boot_index)

###
# Regression code
###

def regression_null(y, city, predict_quant, loss):
    '''
    fit the null model for comparison
    '''
    # train the model
    model = 'average'

    # predict the model
    predict_day = np.ones(len(y['day_test'])) * np.mean(y['day_train'])
    predict_night = np.ones(len(y['night_test'])) * np.mean(y['night_train'])

    # plot predict vs actual
    plot_actualVpredict(y, predict_day, predict_night, 'null', city, predict_quant)

    # calculate the MAE
    mae_day = np.mean(abs(predict_day - y['day_test']))
    mae_night = np.mean(abs(predict_night - y['night_test']))
    # code.interact(local=locals())
    r2_day = r2_score(y['day_test'], predict_day)
    r2_night = r2_score(y['night_test'], predict_night)

    # record results
    loss = loss.append({
        'time_of_day': 'diurnal',
        'hold_num': city,
        'model': model,
        'error_metric': 'r2',
        'error': r2_day
    }, ignore_index=True)
    loss = loss.append({'time_of_day': 'diurnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_day}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_night}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'r2','error': r2_night}, ignore_index=True)

    return(loss)

def regression_gradientboost(X_train, y, X_test, city, predict_quant, loss):
    '''
    fit the GradientBoostingRegressor
    '''
    model = 'gbrf'
    # train the model
    gbm_day_reg = GradientBoostingRegressor(max_depth=2, learning_rate=0.1, n_estimators=500, loss='ls')
    gbm_night_reg = GradientBoostingRegressor(max_depth=2, learning_rate=0.1, n_estimators=500, loss='ls')
    # code.interact(local = locals())
    gbm_day_reg.fit(X_train, y['day_train'])
    gbm_night_reg.fit(X_train, y['night_train'])

    # predict the model
    predict_day = gbm_day_reg.predict(X_test)
    predict_night = gbm_night_reg.predict(X_test)

    # plot predict vs actual
    plot_actualVpredict(y, predict_day, predict_night, 'gbrf', city, predict_quant)

    # calculate the error metrics
    mae_day = np.mean(abs(predict_day - y['day_test']))
    mae_night = np.mean(abs(predict_night - y['night_test']))
    r2_day = r2_score(y['day_test'], predict_day)
    r2_night = r2_score(y['night_test'], predict_night)

    # record results
    loss = loss.append({
        'time_of_day': 'diurnal',
        'hold_num': city,
        'model': model,
        'error_metric': 'r2',
        'error': r2_day
    }, ignore_index=True)
    loss = loss.append({'time_of_day': 'diurnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_day}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_night}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'r2','error': r2_night}, ignore_index=True)

    return(loss)

def regression_linear(X_train, y, X_test, city, predict_quant, loss):
    '''
    fit the multiple linear regressions
    '''
    model = 'mlr'
    # train the model
    mlr_day_reg = LinearRegression()
    mlr_night_reg = LinearRegression()
    mlr_day_reg.fit(X_train, y['day_train'])
    mlr_night_reg.fit(X_train, y['night_train'])


    # predict the model
    predict_day = mlr_day_reg.predict(X_test)
    predict_night = mlr_night_reg.predict(X_test)

    # plot predict vs actual
    plot_actualVpredict(y, predict_day, predict_night, 'mlr', city, predict_quant)

    # calculate the MAE
    mae_day = np.mean(abs(predict_day - y['day_test']))
    mae_night = np.mean(abs(predict_night - y['night_test']))
    r2_day = r2_score(y['day_test'], predict_day)
    r2_night = r2_score(y['night_test'], predict_night)

    # record results
    loss = loss.append({
        'time_of_day': 'diurnal',
        'hold_num': city,
        'model': model,
        'error_metric': 'r2',
        'error': r2_day
    }, ignore_index=True)
    loss = loss.append({'time_of_day': 'diurnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_day}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_night}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'r2','error': r2_night}, ignore_index=True)

    return(loss)

def regression_randomforest(X_train, y, X_test, city, predict_quant, loss):
    '''
    fit the GradientBoostingRegressor
    '''
    model = 'rf'
    # train the model
    reg_day = RandomForestRegressor(n_estimators=500, max_features=1/3)
    reg_night = RandomForestRegressor(n_estimators=500, max_features=1/3)
    reg_day.fit(X_train, y['day_train'])
    reg_night.fit(X_train, y['night_train'])

    # predict the model
    predict_day = reg_day.predict(X_test)
    predict_night = reg_night.predict(X_test)

    # plot predict vs actual
    plot_actualVpredict(y, predict_day, predict_night, 'gbrf', city, predict_quant)

    # calculate the error metrics
    mae_day = np.mean(abs(predict_day - y['day_test']))
    mae_night = np.mean(abs(predict_night - y['night_test']))
    r2_day = r2_score(y['day_test'], predict_day)
    r2_night = r2_score(y['night_test'], predict_night)

    # record results
    loss = loss.append({
        'time_of_day': 'diurnal',
        'hold_num': city,
        'model': model,
        'error_metric': 'r2',
        'error': r2_day
    }, ignore_index=True)
    loss = loss.append({'time_of_day': 'diurnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_day}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_night}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'r2','error': r2_night}, ignore_index=True)

    return(loss)

def regression_mars(X_train, y, X_test, city, predict_quant, loss):
    '''
    fit the GradientBoostingRegressor
    '''
    model = 'mars'
    # train the model
    reg_day = Earth(max_degree=1, penalty=1.0, endspan=5)
    reg_night = Earth(max_degree=1, penalty=1.0, endspan=5)
    reg_day.fit(X_train, y['day_train'])
    reg_night.fit(X_train, y['night_train'])

    # predict the model
    predict_day = reg_day.predict(X_test)
    predict_night = reg_night.predict(X_test)

    # plot predict vs actual
    plot_actualVpredict(y, predict_day, predict_night, 'gbrf', city, predict_quant)

    # calculate the error metrics
    mae_day = np.mean(abs(predict_day - y['day_test']))
    mae_night = np.mean(abs(predict_night - y['night_test']))
    r2_day = r2_score(y['day_test'], predict_day)
    r2_night = r2_score(y['night_test'], predict_night)

    # record results
    loss = loss.append({
        'time_of_day': 'diurnal',
        'hold_num': city,
        'model': model,
        'error_metric': 'r2',
        'error': r2_day
    }, ignore_index=True)
    loss = loss.append({'time_of_day': 'diurnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_day}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_night}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'r2','error': r2_night}, ignore_index=True)

    return(loss)

def regression_gam(X_train, y, X_test, city, predict_quant, loss):
    '''
    fit the GradientBoostingRegressor
    '''
    model = 'gam'
    # train the model
    reg_day = LinearGAM(n_splines=10)
    reg_night = LinearGAM(n_splines=10)
    reg_day.fit(X_train, y['day_train'])
    reg_night.fit(X_train, y['night_train'])

    # predict the model
    predict_day = reg_day.predict(X_test)
    predict_night = reg_night.predict(X_test)

    # plot predict vs actual
    plot_actualVpredict(y, predict_day, predict_night, 'gbrf', city, predict_quant)

    # calculate the error metrics
    mae_day = np.mean(abs(predict_day - y['day_test']))
    mae_night = np.mean(abs(predict_night - y['night_test']))
    r2_day = r2_score(y['day_test'], predict_day)
    r2_night = r2_score(y['night_test'], predict_night)

    # record results
    loss = loss.append({
        'time_of_day': 'diurnal',
        'hold_num': city,
        'model': model,
        'error_metric': 'r2',
        'error': r2_day
    }, ignore_index=True)
    loss = loss.append({'time_of_day': 'diurnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_day}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'mae','error': mae_night}, ignore_index=True)
    loss = loss.append({'time_of_day': 'nocturnal','hold_num': city,'model': model,'error_metric': 'r2','error': r2_night}, ignore_index=True)

    return(loss)

def full_gbm_regression(df, cities, vars_selected=None):
    '''
    fit gbm on the entire dataset and return the objects
    '''
    if vars_selected is None:
        vars_selected = []
    reg_gbm = {}
    reg_gbm['diurnal'] = {}
    reg_gbm['nocturnal'] = {}
    X_train = {}
    predict_quant = 'lst'
    cities = cities.copy()
    cities.append('all')
    for city in cities:
        # subset for the city
        if city != 'all':
            df_city = df[df['city']==city].copy()
        else:
            df_city = df.copy()
        # drop necessary variables
        df_city, response = prepare_lst_prediction(df_city)
        # keep only specified variables, if any were specified
        if len(vars_selected)>0:
            df_city = df_city[vars_selected+['city']]
        # no need to divide, but split into X and y
        X_train[city], X_test, y_train, y_test = split_holdout(df_city, response, test_size=0)#, random_state=RANDOM_SEED)
        print(len(X_train[city]), len(X_test))
        # drop unnecessary variables
        X_train, X_test = subset_regression_data(X_train, X_test)
        # response values
        y = define_response_lst(y_train, y_train)
        # fit the model
        reg_gbm['diurnal'][city] = GradientBoostingRegressor(max_depth=2, learning_rate=0.1, n_estimators=500, loss='ls')
        reg_gbm['diurnal'][city].fit(X_train[city], y['day_train'])
        reg_gbm['nocturnal'][city] = GradientBoostingRegressor(max_depth=2, learning_rate=0.1, n_estimators=500, loss='ls')
        reg_gbm['nocturnal'][city].fit(X_train[city], y['night_train'])
    reg_gbm['covariates'] = X_train[city].columns
    return(reg_gbm, X_train)


###
# Supporting code
###

def split_holdout(df, response, test_size):
    '''
    Prepare spatial holdout
    '''
    # what is the total number of records?
    n_records = df.shape[0]
    # what are the holdout numbers to draw from?
    holdout_freq = df.groupby('holdout')['holdout'].count()
    holdout_options = list(holdout_freq.index)
    # required number of records
    req_records = n_records * (test_size*0.95)
    # select holdout groups until required number of records is achieved
    heldout_records = 0
    heldout_groups = []
    while heldout_records < req_records:
        # randomly select a holdout group to holdout
        hold = np.random.choice(holdout_options, 1, replace = False)[0]
        # remove that from the options
        holdout_options.remove(hold)
        # add that to the heldout list
        heldout_groups.append(hold)
        # calculate the number of records held out
        heldout_records = holdout_freq.loc[heldout_groups].sum()
    # create the test and training sets
    X_test = df[df.holdout.isin(heldout_groups)]
    y_test = response[df.holdout.isin(heldout_groups)]
    X_train = df[~df.holdout.isin(heldout_groups)]
    y_train = response[~df.holdout.isin(heldout_groups)]
    return(X_train, X_test, y_train, y_test)

def loop_variable_selection(df, cities):
    from datetime import datetime
    vars_forward = {}
    vars_forward['day'] = {}
    vars_forward['night'] = {}
    for city in ['all'] + cities:
        for period in ['day','night']:
            print('{}: Starting {}, {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), city, period))
            vars_forward[period][city] = feature_selection(25, city, df, period)
            print('{}: Completed {}, {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), city, period))
    with open('data/variable_selection.pkl', 'wb') as f:
        pickle.dump(vars_forward, f, pickle.HIGHEST_PROTOCOL)

def feature_selection(holdout_num, city, df, period):
    '''
    forward selection of variables based on OOB mae
    '''
    df_set, response = prepare_lst_prediction(df)
    variables = df_set.columns.values
    variables = [var for var in variables if var not in ['city','area']]
    # subset for the city
    if city != 'all':
        df_city = df[df['city']==city].copy()
    else:
        df_city = df.copy()
    # drop necessary variables
    df_city, response = prepare_lst_prediction(df_city)
    # add variables based on which provide the best improvement to lowering MAE
    vars_inc = []
    vars_mae = []
    num_vars = len(variables)
    while len(vars_inc)<num_vars:
        # loop through the Variables
        variables = [var for var in variables if var not in vars_inc]
        variable_mae = pd.DataFrame(index=variables, columns=['mae'])
        for var in variables:
            df_var = df_city.loc[:,[var,'city'] + vars_inc].copy()
            # initialize error measures
            mae = []
            for h in range(holdout_num):
                # no need to divide, but split into X and y
                X_train, X_test, y_train, y_test = split_holdout(df_var, response, test_size=0.25)#, random_state=RANDOM_SEED)
                # drop unnecessary variables
                X_train, X_test = subset_regression_data(X_train.copy(), X_test.copy())
                # response values
                y = define_response_lst(y_train, y_test)
                # fit the model
                gbm_day = GradientBoostingRegressor(max_depth=2, random_state=RANDOM_SEED, learning_rate=0.1, n_estimators=500, loss='ls')
                gbm_day.fit(X_train, y['{}_train'.format(period)])
                # predict the model
                predict_day = gbm_day.predict(X_test)
                # calculate MAE
                mae.append(np.mean(abs(predict_day - y['{}_test'.format(period)])))
            # calculate the average
            variable_mae.loc[var,'mae'] = np.mean(mae)
        # variable to include
        vars_inc.append(variables[variable_mae.loc[:,'mae'].values.argmin()])
        vars_mae.append(variable_mae.loc[:,'mae'].values.min())
    # add to dict
    var_forwardstep = pd.DataFrame({
        'variables':vars_inc,
        'mae':vars_mae
    })
    return(var_forwardstep)


###
# Plotting code
###
def plot_density(df, cities):
    '''
    output density plots of the variables
    '''
    for city in cities:
        # logger.info('density plotting for {}'.format(city))
        df_city = df.loc[df['city']==city]
        # thermal radiance
        df_city['tr_day_mean'].plot(kind='density', label = "diurnal", alpha = 0.5)
        df_city['tr_nght_mean'].plot(kind='density', label = "nocturnal", alpha = 0.5)
        plt.legend(loc='upper right')
        plt.title("Mean {} Thermal Radiance".format(city))
        plt.xlabel('Thermal Radiance [unit?]')
        plt.savefig('fig/working/density/therm-rad_{}.pdf'.format(city), format='pdf', dpi=1000, transparent=True)
        plt.clf()
        #
        # land surface temperature
        df_city['lst_day_mean_mean'].plot(kind='density', label = "diurnal", alpha = 0.5)
        df_city['lst_night_mean_mean'].plot(kind='density', label = "nocturnal", alpha = 0.5)
        plt.legend(loc='upper right')
        plt.title("Mean {} Land Surface Temperature".format(city))
        plt.xlabel('Land Surface Temperature ^oC')
        plt.savefig('fig/working/density/lst_{}.pdf'.format(city), format='pdf', dpi=1000, transparent=True)
        plt.clf()

    # scatter plot thermal radiance against land surface, colored by city
    # bmap = brewer2mpl.get_map('Paired','Qualitative',4).mpl_colors
    with plt.style.context('fivethirtyeight'):
        # f = plt.plot()
        for i in range(len(cities)):
            city = cities[i]
            df_city = df.loc[df['city']==city]
            plt.scatter(df_city['tr_day_mean'], df_city['lst_day_mean_mean'], label = city)#, c = bmap[i])
        plt.legend(loc='lower right')
        plt.title('Diurnal')
        plt.xlabel('Thermal Radiance')
        plt.ylabel('Land Surface Temperature')
        plt.savefig('fig/working/density/lst-vs-tr_day.pdf', format='pdf', dpi=1000, transparent=True)
        plt.clf()

    with plt.style.context('fivethirtyeight'):
        # f = plt.plot()
        for i in range(len(cities)):
            city = cities[i]
            df_city = df.loc[df['city']==city]
            plt.scatter(df_city['tr_nght_mean'], df_city['lst_night_mean_mean'], label = city)#, c = bmap[i])
        plt.legend(loc='lower right')
        plt.title('Nocturnal')
        plt.xlabel('Thermal Radiance')
        plt.ylabel('Land Surface Temperature')
        plt.savefig('fig/working/density/lst-vs-tr_night.pdf', format='pdf', dpi=1000, transparent=True)
        plt.clf()

def plot_holdout_points(loss, grid_size):
    '''
    plot the city holdout validation metrics
    '''
    loss['city'] = loss['hold_num'].str[-3:]
    # with plt.style.context('fivethirtyeight'):
    five_thirty_eight = [
        "#30a2da",
        "#fc4f30",
        "#e5ae38",
        "#6d904f",
        "#8b8b8b",
    ]
    sns.set_palette(five_thirty_eight)
    mpl.rcParams.update({'font.size': 12})
    g = sns.factorplot(y="error", x="time_of_day", hue="city", col = "error_metric", data=loss, sharey = False,
                       row = 'model',
                      linestyles='', markers=['$B$','$D$','$X$','$P$'],
                      hue_order = ['bal', 'det', 'phx', 'por'],
                      ci=None)
    # plt.legend(loc='lower center', ncol=4, frameon=False)
    g.set_titles('{row_name}')
    for i, ax in enumerate(g.axes.flat): # set every-other axis for testing purposes
        if i%2==1:
            ax.set_ylim(0,5)
            ax.set_ylabel('Mean Absolute Error')
            ax.set_xlabel('')
        elif i%2==0:
            ax.set_ylim(-1,1)
            ax.set_ylabel('Out-of-bag R$^2$')
            ax.set_xlabel('')
    plt.savefig('fig/working/regression/cities_holdout_{}.pdf'.format(grid_size), format='pdf', dpi=1000, transparent=True)
    plt.show()
    plt.clf()

def plot_holdouts(loss, grid_size):
    '''
    plot boxplots of holdouts
    '''
    five_thirty_eight = [
        "#30a2da",
        "#fc4f30",
        "#e5ae38",
        "#6d904f",
        "#8b8b8b",
    ]
    sns.set_palette(five_thirty_eight)
    mpl.rcParams.update({'font.size': 12})
    g = sns.catplot(y="error", x="time_of_day", hue="model", col = "error_metric", data=loss, sharey = False, kind="box")
    g.set_titles('')
    for i, ax in enumerate(g.axes.flat): # set every-other axis for testing purposes
        if i%2==1:
            ax.set_ylim(0,1.3)
            ax.set_ylabel('Mean Absolute Error ($^o$C)')
            ax.set_xlabel('')
        elif i%2==0:
            ax.set_ylim(0.5,1)
            ax.set_ylabel('Out-of-bag R$^2$')
            ax.set_xlabel('')
    plt.savefig('fig/working/regression/holdout_results_{}.pdf'.format(grid_size), format='pdf', dpi=500, transparent=True)
    plt.show()
    plt.clf()

def plot_importance(results_swing, grid_size):
    '''
    plot the feature importance of the variables and the cities
    '''
    # order features by nocturnal swing
    feature_order = list(results_swing[results_swing.dependent=='lst_night_mean'].groupby('independent').mean().sort_values(by=('swing'),ascending=False).index)

    # plot
    g = sns.factorplot(x='swing', y='independent', hue='dependent', data=results_swing, kind='bar', col='model', order = feature_order)
    g.set_axis_labels("variable importance (swing)", "")
    g.set_titles("{col_name}")

    # fig = plt.gcf()
    # fig.set_size_inches(15,20)

    plt.savefig('fig/working/regression/variableImportance_{}.pdf'.format(grid_size), format='pdf', dpi=500, transparent=True)
    plt.show()
    plt.clf()
    return(feature_order)

def plot_dependence(importance_order, reg_gbm, cities, X_train, vars_selected, show_plot=False):
    '''
    Plot the partial dependence for the different regressors
    '''
    cities =  cities.copy()
    cities.append('all')
    # plot setup (surely this can be a function)
    five_thirty_eight = [
        "#30a2da",
        "#fc4f30",
        "#e5ae38",
        "#6d904f",
        "#8b8b8b",]
    sns.set_palette(five_thirty_eight)
    mpl.rcParams.update({'font.size': 20})
    # init subplots (left is nocturnal, right is diurnal)
    fig, axes = plt.subplots(6, 2, figsize = (15,30), sharey=True)#'row')
    # loop through the top n variables by nocturnal importance
    feature = 0
    for var_dependent in importance_order:
        left_right = 0
        for period in ['nocturnal', 'diurnal']:
            for city in cities:
                gbm = reg_gbm[period][city]
                # feature position
                feature_num = vars_selected.index(var_dependent)
                # calculate the partial dependence
                y, x = partial_dependence(gbm, feature_num, X = X_train[city],
                                        grid_resolution = 100)
                # add the line to the plot
                if city=='all':
                    axes[feature, left_right].plot(x[0],y[0],label=city, linestyle='--', color='#8b8b8b')
                else:
                    axes[feature, left_right].plot(x[0],y[0],label=city)
                # add the label to the plot
                axes[feature, left_right].set_xlabel(var_dependent)
            left_right += 1
        feature += 1
    # legend
    handles, labels = axes[0,0].get_legend_handles_labels()
    # l = plt.legend(handles[0:5], labels[0:5], loc='lower left')
    fig.legend(handles[0:5], labels[0:5], loc='lower center', bbox_to_anchor=(0.5,-0.007),
              fancybox=True, shadow=True, ncol=5)
    # save the figure
    fig.tight_layout()
    if show_plot:
        fig.show()
    else:
        fig.savefig('fig/working/partial_dependence.pdf', format='pdf', dpi=1000, transparent=True)
        fig.clf()

def scatter_lst(df, cities):
    '''
    scatter lst night vs day
    '''

    # scatter plot thermal radiance against land surface, colored by city
    # bmap = brewer2mpl.get_map('Paired','Qualitative',4).mpl_colors
    with plt.style.context('fivethirtyeight'):
        for i in range(len(cities)):
            city = cities[i]
            df_city = df.loc[df['city']==city]
            plt.scatter(df_city['lst_day_mean_mean'], df_city['lst_night_mean_mean'], label = city, alpha = 0.5)
        plt.legend(loc='lower right')
        plt.xlabel('Day LST ($^o$C)')
        plt.ylabel('Night LST ($^o$C)')
        plt.text(20, 40,'Correlation = {0:.2f}'.format(df_city['lst_day_mean_mean'].corr(df_city['lst_night_mean_mean'])), ha='left', va='top')
        plt.savefig('fig/working/density/lst_night-vs-day.pdf', format='pdf', dpi=300, transparent=True)
        plt.clf()

def joyplot_lst(df, cities):
    '''
    scatter lst night vs day
    '''

    # scatter plot thermal radiance against land surface, colored by city
    # bmap = brewer2mpl.get_map('Paired','Qualitative',4).mpl_colors
    import joypy
    df1 = df[['lst_night_mean_mean','lst_day_mean_mean','city']]
    df1 = df1.rename(index=str, columns={"lst_night_mean_mean": "night", "lst_day_mean_mean": "day"})
    df1 = df1.replace([np.inf, -np.inf], np.nan)
    df1 = df1.dropna(axis=0, how='any')
    with plt.style.context('fivethirtyeight'):
        fig, axes = joypy.joyplot(df1, by='city', ylim='own',legend=True)
        plt.xlabel('Land Surface Temperature ($^o$C)')
    plt.savefig('fig/working/density/joyplot_lst.pdf', format='pdf', dpi=300, transparent=True)
    plt.clf()

def plot_actualVpredict(y, predict_day, predict_night, model, city, target):
    '''
    plot a scatter of predicted vs actual points
    '''
    xy_line = (np.min([y['night_test'],y['day_test']]),np.max([y['night_test'],y['day_test']]))
    with plt.style.context('fivethirtyeight'):
        plt.scatter(y['day_test'], predict_day, label = 'Diurnal')
        plt.scatter(y['night_test'], predict_night, label = 'Nocturnal')
        plt.plot(xy_line,xy_line, 'k--')
        plt.ylabel('Predicted')
        plt.xlabel('Actual')
        plt.legend(loc='lower right')
        plt.title('Gradient Boosted Trees \n {}'.format(city))
        plt.savefig('fig/working/regression/actualVpredict_{}_{}_{}.pdf'.format(target, model, city), format='pdf', dpi=1000, transparent=True)
        plt.clf()


if __name__ == '__main__':
    # profile() # initialise the board
    main()
