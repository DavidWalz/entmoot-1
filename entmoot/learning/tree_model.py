import numpy as np

from sklearn.base import clone
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.utils import check_random_state

import copy
import sys


class EntingRegressor(BaseEstimator, RegressorMixin):
    """Predict with LightGBM tree model and include model uncertainty 
    defined by distance-based standard estimator.


    Parameters
    ----------
    base_estimator : LGBMRegressor instance, EntingRegressor instance or 
        None (default). If LGBMRegressor instance of None is given: new 
        EntingRegressor is defined. If EntingRegressor is given: base_estimator
        and std_estimator are given to new instance.
    std_estimator : DistanceBasedStd instance,
        Determines which measure is used to capture uncertainty.
    random_state : int, RandomState instance, or None (default)
        Set random state to something other than None for reproducible
        results.
    """

    def __init__(self, base_estimator=None,
                std_estimator=None,
                random_state=None,
                cat_idx=[]):

        self.random_state = random_state
        self.base_estimator = base_estimator
        self.std_estimator = std_estimator
        self.cat_idx = cat_idx

        # check if base_estimator is EntingRegressor
        if isinstance(base_estimator, EntingRegressor):
            self.base_estimator = base_estimator.base_estimator
            self.std_estimator = base_estimator.std_estimator

    def fit(self, X, y):
        """Fit model and standard estimator to observations.

        Parameters
        ----------
        X : array-like, shape=(n_samples, n_features)
            Training vectors, where `n_samples` is the number of samples
            and `n_features` is the number of features.

        y : array-like, shape=(n_samples,)
            Target values (real numbers in regression)

        Returns
        -------
        -
        """
        base_estimator = self.base_estimator

        # suppress lgbm output
        base_estimator.set_params(
            random_state=self.random_state,
            verbose=-1
        )

        # clone base_estimator (only supported for sklearn estimators)
        self.regressor_ = clone(base_estimator)

        # update std estimator
        self.std_estimator.update(X, y, cat_column=self.cat_idx)

        # update tree model regressor
        import warnings
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self.cat_idx:
                self.regressor_.fit(X, y, categorical_feature=self.cat_idx)
            else:
                self.regressor_.fit(X, y)

    def set_params(self, **params):
        """Sets parameters related to tree model estimator. All parameter 
        options for LightGBM are given here: 
            https://lightgbm.readthedocs.io/en/latest/Parameters.html

        Parameters
        ----------
        kwargs : dict
            Additional arguments to be passed to the tree model

        Returns
        -------
        -
        """
        if not "min_child_samples" in params.keys():
            params.update({"min_child_samples":2})
            
        self.base_estimator.set_params(**params)

    def predict(self, X, return_std=False, scaled=True):
        """Predict.

        If `return_std` is set to False, only tree model prediction is returned.
        Return mean and predicted standard deviation, which is approximated 
        based on standard estimator specified, when `return_std` is set to True. 

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            where `n_samples` is the number of samples
            and `n_features` is the number of features.

        Returns
        -------
        mean or (mean, std): np.array, shape (n_rows, n_dims) 
            or tuple(np.array, np.array), depending on value of `return_std`.
        """
        mean = self.regressor_.predict(X)

        if return_std:
            std = self.std_estimator.predict(X,scaled=scaled)
            return mean, std

        # return the mean
        return mean

    def get_gbm_model(self):
        """
        Returns `GbmModel` instance of the tree model.

        Parameters
        ----------
        -

        Returns
        -------
        gbm_model : `GbmModel`
            ENTMOOT native tree model format to formulate optimization model
        """

        from entmoot.learning.lgbm_processing import order_tree_model_dict
        from entmoot.learning.gbm_model import GbmModel

        original_tree_model_dict = self.regressor_._Booster.dump_model()

        import json
        with open('tree_dict_next.json', 'w') as f:
            json.dump(
                original_tree_model_dict, 
                f, 
                indent=4, 
                sort_keys=False
            )

        ordered_tree_model_dict = \
            order_tree_model_dict(
                original_tree_model_dict,
                cat_column=self.cat_idx
            )

        gbm_model = GbmModel(ordered_tree_model_dict)
        return gbm_model

class MisicRegressor(EntingRegressor):

    def __init__(self, base_estimator=None,
                std_estimator=None,
                random_state=None,
                cat_idx=[]):

        self.random_state = random_state
        self.base_estimator = base_estimator
        self.std_estimator = std_estimator
        self.cat_idx = cat_idx

        # check if base_estimator is EntingRegressor
        if isinstance(base_estimator, MisicRegressor):
            self.base_estimator = base_estimator.base_estimator
            self.std_estimator = base_estimator.std_estimator

    def fit(self, X, y):
        """Fit model and standard estimator to observations.

        Parameters
        ----------
        X : array-like, shape=(n_samples, n_features)
            Training vectors, where `n_samples` is the number of samples
            and `n_features` is the number of features.

        y : array-like, shape=(n_samples,)
            Target values (real numbers in regression)

        Returns
        -------
        -
        """
        base_estimator = self.base_estimator

        # suppress lgbm output
        base_estimator.set_params(
            random_state=self.random_state,
            verbose=-1
        )

        # clone base_estimator (only supported for sklearn estimators)
        self.regressor_ = clone(base_estimator)

        # update tree model regressor
        import warnings
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self.cat_idx:
                self.regressor_.fit(X, y, categorical_feature=self.cat_idx)
            else:
                self.regressor_.fit(X, y)

        gbm_model = self.get_gbm_model()

        # update std estimator
        self.std_estimator.update(X, y, gbm_model, cat_column=self.cat_idx)