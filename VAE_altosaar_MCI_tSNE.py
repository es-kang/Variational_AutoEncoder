import itertools
import matplotlib as mpl
from matplotlib import pyplot as plt

import pandas as pd
import numpy as np

import os
import sklearn
from sklearn import preprocessing
from sklearn.preprocessing import normalize
from sklearn.manifold import TSNE
import tensorflow as tf
import tensorflow.contrib.slim as slim
import tensorflow.contrib.distributions as distributions

import seaborn as sns

import scipy.io
from scipy.misc import imsave

import random
import time
import tsne

# For MCI dataset
#Original file was mat file

np.random.seed(0)
tf.set_random_seed(0)

data = scipy.io.loadmat('/home/eunsongk/Data/ADNI/ADNI_eMCI_AAL116ROI_TimeSeries(0.01-0.08).mat')["aal116ROITimeSeries"]
labels = scipy.io.loadmat('/home/eunsongk/Data/ADNI/ADNI_eMCI_AAL116ROI_TimeSeries(0.01-0.08).mat')["labels"]
# print(data.shape)
#(62,1)
labels = np.array([labels]*130).transpose()
labels = np.asarray(labels).ravel()
labels = np.asarray(labels)


#(8060,)


arr = np.empty((data.shape[0], data[0, 0].shape[0], data[0, 0].shape[1]))
# print(arr.shape)
#(62, 130, 116)

for dat, cnt in zip(data[:, 0], np.arange(arr.shape[0])):
    arr[cnt] = dat
arr = arr.reshape(-1, arr.shape[-1])
# print(arr.shape)
# (8060,116)

#Gaussian normalization
arr-=np.mean(arr)
arr/=np.std(arr)

# norm1 = x / np.linalg.norm(x)
# norm2 = normalize(arr[:, np.newaxis], axis=1).ravel()
# print(norm2)
# print np.all(norm1 == norm2)

#norm1 = arr / np.linalg.norm(arr)
norm2 = normalize(arr, norm='l2', axis=1, copy=True, return_norm=False)
arr_tSNE = norm2

# random.shuffle(arr)
# train_data = arr[:6448]
# test_data = arr[6448:]
#
# arr = train_data
# arr2 = test_data
#
# # random.shuffle(labels)
# training_label = labels[:6448]
# test_label = labels[6448:]
# test_label[test_label==-1]=0

test_label_tSNE = labels
test_label_tSNE[test_label_tSNE==-1]=0


# Label one hot encoding
def one_hot(j):
    e = np.zeros(2)
    e[j] = 1
    return e
test_label = [one_hot(int(x)) for x in test_label_tSNE[:]]

# test_label = np.asarray(test_label)
labels = np.array(test_label)


random.shuffle(arr)
train_data = arr_tSNE[:6448]
test_data = arr_tSNE[6448:]

arr = train_data
arr2 = test_data

random.shuffle(labels)
training_label = labels[:6448]
test_label = labels[6448:]

input_dim = 116
n_samples = arr.shape[0]
# # 6448
n_samples2 = arr2.shape[0]
# # 1612


# For plot
# sns.set_style('whitegrid')
# sns.set_context("notebook", font_scale=1.5,
#                 rc={"lines.linewidth": 2.5})

sg = tf.contrib.bayesflow.stochastic_graph
st = tf.contrib.bayesflow.stochastic_tensor
# distributions = tf.contrib.distributions


flags = tf.app.flags
flags.DEFINE_string('data_dir', '/tmp/dat/', 'Directory for data')
flags.DEFINE_string('logdir', '/tmp/log/', 'Directory for logs')

# For making plots:
# flags.DEFINE_integer('latent_dim', 2, 'Latent dimensionality of model')
# flags.DEFINE_integer('batch_size', 64, 'Minibatch size')
# flags.DEFINE_integer('n_samples', 10, 'Number of samples to save')
# flags.DEFINE_integer('print_every', 10, 'Print every n iterations')
# flags.DEFINE_integer('hidden_size', 200, 'Hidden size for neural networks')
# flags.DEFINE_integer('n_iterations', 1000, 'number of iterations')

# For bigger model:
flags.DEFINE_integer('latent_dim', 20, 'Latent dimensionality of model')
flags.DEFINE_integer('batch_size', 13, 'Minibatch size')
flags.DEFINE_integer('n_samples', 10, 'Number of samples to save')
flags.DEFINE_integer('print_every', 50, 'Print every n iterations')
flags.DEFINE_integer('hidden_size', 40, 'Hidden size for neural networks')
flags.DEFINE_integer('n_iterations', 10, 'number of iterations')

FLAGS = flags.FLAGS


def inference_network(x, latent_dim, hidden_size):
  """Construct an inference network parametrizing a Gaussian.

  Args:
    x: A batch of MNIST digits.
    latent_dim: The latent dimensionality.
    hidden_size: The size of the neural net hidden layers.

  Returns:
    mu: Mean parameters for the variational family Normal
    sigma: Standard deviation parameters for the variational family Normal
  """
  with slim.arg_scope([slim.fully_connected], activation_fn=tf.nn.relu):
    net = slim.flatten(x)
    net = slim.fully_connected(net, hidden_size)
    net = slim.fully_connected(net, hidden_size)
    gaussian_params = slim.fully_connected(net, latent_dim * 2, activation_fn=None)

  # The mean parameter is unconstrained
    mu = gaussian_params[:, :latent_dim]
    # The standard deviation must be positive. Parametrize with a softplus and
    # add a small epsilon for numerical stability
    sigma = 1e-6 + tf.nn.softplus(gaussian_params[:, latent_dim:])
    return mu, sigma


def generative_network(z, hidden_size):
  """Build a generative network parametrizing the likelihood of the data

  Args:
    z: Samples of latent variables
    hidden_size: Size of the hidden state of the neural net

  Returns:
    mu: Mean parameters for the variational family Normal
    sigma: Standard deviation parameters for the variational family Normal
  """
  # with slim.arg_scope([slim.fully_connected], activation_fn=tf.nn.relu):
  #   net = slim.fully_connected(z, hidden_size)
  #   net = slim.fully_connected(net, hidden_size)
  #   gaussian_params = slim.fully_connected(net, input_dim*2, activation_fn=None)
  #   mu = gaussian_params[:, :input_dim]
  #   sigma = gaussian_params[:, input_dim:]
  #   mu = tf.reshape(mu, [-1, 116])
  #   sigma = tf.reshape(sigma, [-1, 116])
  #   return mu, sigma
  #
  with slim.arg_scope([slim.fully_connected], activation_fn=tf.nn.relu):
    net = slim.fully_connected(z, hidden_size)
    net = slim.fully_connected(net, hidden_size)
    gaussian_params = slim.fully_connected(net, input_dim*2, activation_fn=None)
    mu = gaussian_params[:, :input_dim]
    sigma = 1e-6 + tf.nn.softplus(gaussian_params[:, input_dim:])
    mu = tf.reshape(mu, [-1, 116, 1])
    # mu = tf.reshape(mu, [-1, 116])
    sigma = tf.reshape(sigma, [-1, 116, 1])
    # sigma = tf.reshape(sigma, [-1, 116])
    return mu, sigma

def train():
  # Input placeholders
  with tf.name_scope('arr'):
     x = tf.placeholder(tf.float32, [None, input_dim, 1])
     # x = tf.placeholder(tf.float32, [None, input_dim,1])
     # tf.summary.image('arr', x)

  with tf.variable_scope('variational'):
    q_mu, q_sigma = inference_network(x=x,
                                      latent_dim=FLAGS.latent_dim,
                                      hidden_size=FLAGS.hidden_size)
    with st.value_type(st.SampleValue()):
      # The variational distribution is a Normal with mean and standard
      # deviation given by the inference network
      q_z = st.StochasticTensor(distributions.MultivariateNormalDiag(mu=q_mu, diag_stdev=q_sigma))



  with tf.variable_scope('model'):
    # The likelihood is Bernoulli-distributed with logits given by the generative network
    p_x_given_z_mu, p_x_given_z_sigma = generative_network(z=q_z,
                                            hidden_size=FLAGS.hidden_size)
    p_x_given_z = distributions.MultivariateNormalDiag(mu=p_x_given_z_mu, diag_stdev = p_x_given_z_sigma)
    posterior_predictive_samples = p_x_given_z.sample()
    # tf.summary.image('posterior_predictive', tf.cast(posterior_predictive_samples, tf.float32))

  # Take samples from the prior
  with tf.variable_scope('model', reuse=True):
    p_z = distributions.MultivariateNormalDiag(mu=np.zeros(FLAGS.latent_dim, dtype=np.float32),
                                               diag_stdev=np.ones(FLAGS.latent_dim, dtype=np.float32))
    p_z_sample = p_z.sample_n(FLAGS.n_samples)
    p_z_sample2 = p_z.sample_n(n_samples2)
    p_x_given_z_mu, p_x_given_z_sigma = generative_network(z=p_z_sample2,
                                            hidden_size=FLAGS.hidden_size)
    prior_predictive = distributions.MultivariateNormalDiag(mu=p_x_given_z_mu, diag_stdev = p_x_given_z_sigma)
    prior_predictive_samples = prior_predictive.sample()
    # tf.summary.image('prior_predictive', tf.cast(prior_predictive_samples, tf.float32))


  # Take samples from the prior with a placeholder
  with tf.variable_scope('model', reuse=True):
    z_input = tf.placeholder(tf.float32, [None, FLAGS.latent_dim])
    p_x_given_z_mu, p_x_given_z_sigma= generative_network(z=z_input,
                                            hidden_size=FLAGS.hidden_size)
    prior_predictive_inp = distributions.MultivariateNormalDiag(mu=p_x_given_z_mu, diag_stdev = p_x_given_z_sigma)

    prior_predictive_inp_sample = prior_predictive_inp.sample()

#################################################################################################
    # for i in range(FLAGS.n_iterations * (n_samples2 // FLAGS.batch_size)):
    #     offset = (i) % (n_samples2 // FLAGS.batch_size)
    #     np_x_fixed = arr2[offset * FLAGS.batch_size:(offset + 1) * FLAGS.batch_size].reshape(-1, input_dim, 1)
    #     #
    #     np_y = test_label[offset * FLAGS.batch_size:(offset + 1) * FLAGS.batch_size]
    #     #  # np_x_fixed = np_x_fixed.reshape((FLAGS.batch_size), 116, 1)
    #     #  # np_x_fixed = (np_x_fixed > 0.5).astype(np.float32)

    # Build the evidence lower bound (ELBO) or the negative loss
    kl = distributions.kl(q_z.distribution, p_z)
    expected_log_likelihood = tf.reduce_sum(p_x_given_z.log_prob(x), -1)
    elbo = tf.reduce_sum(expected_log_likelihood-kl, 0)

    optimizer = tf.train.RMSPropOptimizer(learning_rate=0.0001)
    train_op = optimizer.minimize(-elbo)
    # train_op = optimizer.minimize(elbo)
    tf.scalar_summary("ELBO", elbo)

    # Merge all the summaries

    summary_op = tf.summary.merge_all()

    init_op = tf.global_variables_initializer()

    # Run training
    sess = tf.InteractiveSession()
    sess.run(init_op)


    print('Saving TensorBoard summaries and images to: %s' % FLAGS.logdir)
    train_writer = tf.summary.FileWriter(FLAGS.logdir, sess.graph)


    for i in range(FLAGS.n_iterations*(n_samples//FLAGS.batch_size)):
      offset = (i)%(n_samples//FLAGS.batch_size)
      # Re-binarize the data at every batch; this improves results
      # Original
      #np_x = arr[offset * FLAGS.batch_size:(offset + 1) * FLAGS.batch_size].reshape(-1,input_dim, 1)
      np_x = arr2[offset*FLAGS.batch_size:(offset+1)*FLAGS.batch_size].reshape(-1, input_dim, 1)
      np_y = test_label[offset * FLAGS.batch_size:(offset + 1) * FLAGS.batch_size].reshape(-1, 2, 1)
      # np_x = np_x.reshape(FLAGS.batch_size, 28, 28, 1)
      # np_x = (np_x > 0.5).astype(np.float32)
      sess.run(train_op, {x: np_x})


      # Print progress and save samples every so often
      t0 = time.time()
      if i % FLAGS.print_every == 0:
          np_elbo, summary_str = sess.run([elbo, summary_op], {x: np_x})
          train_writer.add_summary(summary_str, i)
          print('Iteration: {0:d} ELBO: {1:.3f} Examples/s: {2:.3e}'.format(i, np_elbo / FLAGS.batch_size, FLAGS.batch_size * FLAGS.print_every / (time.time() - t0)))
          t0 = time.time()

        # Save samples
        #   np_prior_samples = sess.run(prior_predictive_samples, {x: np_x})
          # if __name__ == "__main__":

          print "Run Y = tsne.tsne(X, no_dims, perplexity) to perform t-SNE on your dataset."
          print "Running example oz_inputn 2,500 MNIST digits..."
          a = (n_samples2, FLAGS.latent_dim)
          np_z = np.zeros(a, dtype=np.float32)
          print(np_z.shape)
          X = sess.run(prior_predictive_inp_sample, {z_input: p_z_sample2})
          # X = z_input.eval()
          # X = p_z_sample2.eval()
          # X = X.reshape(-1, FLAGS.latent_dim)
          # X= prior_predictive_samples.eval().reshape(-1, input_dim)
          # X =  prior_predictive_inp_sample.eval()
          print(X.shape)
          labels = test_label
          print(labels.shape)
          Y =tsne.tsne(X, 2, 20, 30.0)
          np.save('Error.npy', Y)
          cmap = plt.get_cmap('jet', 2)
          plt.scatter(Y[:, 0], Y[:, 1], 20, c=np.argmax(labels, 1), cmap=cmap)
          plt.savefig(os.path.join(FLAGS.logdir, 'tSNE_map_frame_%d.png' % i))
          # plt.scatter(Y[:,0], Y[:,1], 20, c=np.argmax(np_y, 1), cmap=cmap )
          plt.close()




def main(_):
  if tf.gfile.Exists(FLAGS.logdir):
     tf.gfile.DeleteRecursively(FLAGS.logdir)
  tf.gfile.MakeDirs(FLAGS.logdir)
  train()

if __name__ == '__main__':
  tf.app.run()

