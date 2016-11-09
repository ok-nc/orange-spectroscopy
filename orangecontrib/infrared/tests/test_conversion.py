import unittest

import numpy as np
import Orange
from Orange.classification import LogisticRegressionLearner
from Orange.evaluation.testing import TestOnTestData
from Orange.evaluation.scoring import AUC

import sklearn.model_selection as ms

from orangecontrib.infrared.preprocess import Interpolate, \
    Cut, SavitzkyGolayFiltering, Transmittance, Absorbance
from orangecontrib.infrared.data import getx


def separate_learn_test(data):
    sf = ms.ShuffleSplit(n_splits=1, test_size=0.2, random_state=np.random.RandomState(0))
    (traini, testi), = sf.split(y=data.Y, X=data.X)
    return data[traini], data[testi]


def destroy_atts_conversion(data):
    natts = [ a.copy() for a in data.domain.attributes ]
    ndomain = Orange.data.Domain(natts, data.domain.class_vars,
                                metas=data.domain.metas)
    ndata = Orange.data.Table(ndomain, data)
    ndata.X = data.X
    return ndata


def odd_attr(data):
    natts = [a for i, a in enumerate(data.domain.attributes)
            if i%2 == 0]
    ndomain = Orange.data.Domain(natts, data.domain.class_vars,
                                metas=data.domain.metas)
    return Orange.data.Table(ndomain, data)




class TestConversion(unittest.TestCase):

    PREPROCESSORS = [Interpolate(np.linspace(1000, 1800, 100)),
                     SavitzkyGolayFiltering(window=9, polyorder=2, deriv=2),
                     Cut(lowlim=1000, highlim=1800),
                     Absorbance(),
                     Transmittance()]

    @classmethod
    def setUpClass(cls):
        cls.collagen = Orange.data.Table("collagen")

    def test_predict_same_domain(self):
        train, test = separate_learn_test(self.collagen)
        auc = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        self.assertGreater(auc, 0.9) # easy dataset

    def test_predict_samename_domain(self):
        train, test = separate_learn_test(self.collagen)
        test = destroy_atts_conversion(test)
        aucdestroyed = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        self.assertTrue(0.45 < aucdestroyed < 0.55)

    def test_predict_samename_domain_interpolation(self):
        train, test = separate_learn_test(self.collagen)
        aucorig = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        test = destroy_atts_conversion(test)
        train = Interpolate(train, points=getx(train)) # make train capable of interpolation
        auc = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        self.assertEqual(aucorig, auc)

    def test_predict_different_domain(self):
        train, test = separate_learn_test(self.collagen)
        test = Interpolate(points=getx(test) - 1)(test) # other test domain
        aucdestroyed = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        self.assertTrue(0.45 < aucdestroyed < 0.55)

    def test_predict_different_domain_interpolation(self):
        train, test = separate_learn_test(self.collagen)
        aucorig = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        test = Interpolate(points=getx(test) - 1.)(test) # other test domain
        train = Interpolate(points=getx(train))(train)  # make train capable of interpolation
        aucshift = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        self.assertEqual(aucorig, aucshift)
        test = Cut(1000, 1700)(test)
        auccut1 = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        test = Cut(1100, 1600)(test)
        auccut2 = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        test = Cut(1200, 1500)(test)
        auccut3 = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        # the more we cut the lower precision we get
        self.assertTrue(aucorig > auccut1 > auccut2 > auccut3)

    def test_whole_and_train_separete(self):
        """ Applying a preprocessor before spliting data into train and test
        and applying is just on train data should yield the same transformation of
        the test data. """
        data = self.collagen
        for proc in self.PREPROCESSORS:
            train1, test1 = separate_learn_test(proc(data))
            train, test = separate_learn_test(data)
            train = proc(train)
            test_transformed = Orange.data.Table(train.domain, test)
            np.testing.assert_equal(test_transformed.X, test1.X)
            aucorig = AUC(TestOnTestData(train1, test1, [LogisticRegressionLearner]))
            aucnow = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
            self.assertEqual(aucorig, aucnow)

    def test_predict_savgov_same_domain(self):
        data = SavitzkyGolayFiltering(window=9, polyorder=2, deriv=2)(self.collagen)
        train, test = separate_learn_test(data)
        auc = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
        self.assertGreater(auc, 0.85)

    def test_slightly_different_domain(self):
        """ If test data has a slightly different domain then (with interpolation)
        we should obtain a similar classification score. """
        for proc in self.PREPROCESSORS:
            train, test = separate_learn_test(self.collagen)
            train1 = proc(train)
            aucorig = AUC(TestOnTestData(train1, test, [LogisticRegressionLearner]))
            test = destroy_atts_conversion(test)
            test = odd_attr(test)
            train = Interpolate(points=getx(train))(train)  # make train capable of interpolation
            train = proc(train)
            aucnow = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
            self.assertAlmostEqual(aucnow, aucorig, delta=0.01)
            test = Interpolate(points=getx(test) - 1.)(test)  # also do a shift
            aucnow = AUC(TestOnTestData(train, test, [LogisticRegressionLearner]))
            self.assertAlmostEqual(aucnow, aucorig, delta=0.01)  # the difference should be slight