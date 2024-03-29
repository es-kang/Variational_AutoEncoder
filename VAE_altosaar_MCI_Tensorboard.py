import itertools
import matplotlib as plt
import numpy as np
import os

import sklearn
import tensorflow as tf
import tensorflow.contrib.slim as slim
import time
import seaborn as sns
import scipy.io
from sklearn import preprocessing
from sklearn.preprocessing import normalize
from matplotlib import pyplot as plt
from scipy.misc import imsave

import random


#For MCI dataset
#Original file was mat file

# np.random.seed(0)
# tf.set_random_seed(0)

data = scipy.io.loadmat('/home/eunsongk/Data/ADNI/ADNI_eMCI_AAL116ROI_TimeSeries(0.01-0.08).mat')["aal116ROITimeSeries"]
labels = scipy.io.loadmat('/home/eunsongk/Data/ADNI/ADNI_eMCI_AAL116ROI_TimeSeries(0.01-0.08).mat')["labels"]

# print(data.shape)
#(62,1)
labels = np.array([labels]*130).transpose()
labels = np.asarray(labels).ravel()

#print(labels.shape)



arr = np.empty((data.shape[0], data[0, 0].shape[0], data[0, 0].shape[1]))

# print(arr.shape)
#(62, 130, 116)

for dat, cnt in zip(data[:, 0], np.arange(arr.shape[0])):
    arr[cnt] = dat

#Original
arr = arr.reshape(-1, arr.shape[-1])



#arr = arr[cnt].reshape(-1, arr[cnt].shape[1])
#print(arr.ndim)

#Gaussian normalization
arr-=np.mean(arr)
arr/=np.std(arr)
# arr-=np.mean(arr)
# arr/=np.std(arr)

# x = np.random.rand(1000)*10
# norm1 = x / np.linalg.norm(x)
# norm2 = normalize(arr[:, np.newaxis], axis=1).ravel()
# print(norm2)
# print np.all(norm1 == norm2)

#norm1 = arr / np.linalg.norm(arr)
norm2 = normalize(arr, norm='l2', axis=1, copy=True, return_norm=False)
arr = norm2
data = arr


# random.shuffle(arr)

train_data = arr[:6448]
test_data = arr[6448:]

arr = train_data
arr2 = test_data

# random.shuffle(labels)
training_label = labels[:6448]
test_label = labels[6448:]

test_label[test_label==-1]=0



def one_hot(j):
    e = np.zeros((2, 1))
    e[j] = 1
    return e
test_label = [one_hot(int(x)) for x in test_label[:]]




input_dim = 116
n_samples = arr.shape[0]


sns.set_style('whitegrid')

sg = tf.contrib.bayesflow.stochastic_graph
st = tf.contrib.bayesflow.stochastic_tensor
distributions = tf.contrib.distributions


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
flags.DEFINE_integer('latent_dim', 10, 'Latent dimensionality of model')
flags.DEFINE_integer('batch_size', 4, 'Minibatch size')
flags.DEFINE_integer('n_samples', 1, 'Number of samples to save')
flags.DEFINE_integer('print_every', 1, 'Print every n iterations')
flags.DEFINE_integer('hidden_size', 20, 'Hidden size for neural networks')
flags.DEFINE_integer('n_iterations', 1, 'number of iterations')

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
    gaussian_params = slim.fully_connected(
        net, latent_dim * 2, activation_fn=None)
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
    bernoulli_logits: logits for the Bernoulli likelihood of the data
  """
  with slim.arg_scope([slim.fully_connected], activation_fn=tf.nn.relu):
    net = slim.fully_connected(z, hidden_size)
    net = slim.fully_connected(net, hidden_size)
    bernoulli_logits = slim.fully_connected(net, input_dim, activation_fn=None)
    bernoulli_logits = tf.reshape(bernoulli_logits, [-1, 116, 1])
    #bernoulli_logits = tf.reshape(bernoulli_logits, [-1, 1, 116, 1])
  return bernoulli_logits


def train():
  # Train a Variational Autoencoder on MNIST

  # Input placeholders
  with tf.name_scope('arr'):
     x = tf.placeholder(tf.float32, [None, input_dim,  1])
    #x = tf.placeholder(tf.float32, [None, 1, 116, 1])
    # tf.summary.image('arr', x)


  with tf.variable_scope('variational'):
    q_mu, q_sigma = inference_network(x=x,
                                      latent_dim=FLAGS.latent_dim,
                                      hidden_size=FLAGS.hidden_size)
    with st.value_type(st.SampleValue()):
      # The variational distribution is a Normal with mean and standard
      # deviation given by the inference network
      q_z = st.StochasticTensor(distributions.Normal(mu=q_mu, sigma=q_sigma))

  with tf.variable_scope('model'):
    # The likelihood is Bernoulli-distributed with logits given by the
    # generative network
    p_x_given_z_logits = generative_network(z=q_z,
                                            hidden_size=FLAGS.hidden_size)
    p_x_given_z = distributions.Bernoulli(logits=p_x_given_z_logits)
    posterior_predictive_samples = p_x_given_z.sample()
    # tf.summary.image('posterior_predictive',
    #                   tf.cast(posterior_predictive_samples, tf.float32))

  # Take samples from the prior
  with tf.variable_scope('model', reuse=True):
    p_z = distributions.Normal(mu=np.zeros(FLAGS.latent_dim, dtype=np.float32),
                               sigma=np.ones(FLAGS.latent_dim, dtype=np.float32))
    p_z_sample = p_z.sample_n(FLAGS.n_samples)
    p_x_given_z_logits = generative_network(z=p_z_sample,
                                            hidden_size=FLAGS.hidden_size)
    prior_predictive = distributions.Bernoulli(logits=p_x_given_z_logits)
    prior_predictive_samples = prior_predictive.sample()
    # tf.summary.image('prior_predictive',
    #                   tf.cast(prior_predictive_samples, tf.float32))

  # Take samples from the prior with a placeholder
  with tf.variable_scope('model', reuse=True):
    z_input = tf.placeholder(tf.float32, [None, FLAGS.latent_dim])
    p_x_given_z_logits = generative_network(z=z_input,
                                            hidden_size=FLAGS.hidden_size)
    prior_predictive_inp = distributions.Bernoulli(logits=p_x_given_z_logits)
    prior_predictive_inp_sample = prior_predictive_inp.sample()

  # Build the evidence lower bound (ELBO) or the negative loss
  kl = tf.reduce_sum(distributions.kl(q_z.distribution, p_z), 1)
  #Original
  expected_log_likelihood = tf.reduce_sum(p_x_given_z.log_pmf(x),
                                           [-2, -1])
  #expected_log_likelihood = tf.reduce_sum(p_x_given_z.log_pmf(x),
  #                                        [1, 2, 3])
  elbo = tf.reduce_sum(expected_log_likelihood - kl, 0)

  optimizer = tf.train.RMSPropOptimizer(learning_rate=0.001)

  train_op = optimizer.minimize(-elbo)

  # Merge all the summaries
  tf.scalar_summary("ELBO", elbo)
  summary_op = tf.summary.merge_all()

  init_op = tf.global_variables_initializer()

  # Run training
  sess = tf.InteractiveSession()
  sess.run(init_op)






  print('Saving TensorBoard summaries and images to: %s' % FLAGS.logdir)
  train_writer = tf.summary.FileWriter(FLAGS.logdir, sess.graph)

  # # Get fixed MNIST digits for plotting posterior means during training
  # for i in range(FLAGS.n_iterations*(test_data.size//FLAGS.batch_size)):
  #   offset = (i)%(test_data.size//FLAGS.batch_size)
  #   np_x_fixed = arr2[offset * FLAGS.batch_size:(offset + 1) * FLAGS.batch_size].reshape(-1, input_dim, 1)
  #   np_y = test_label[offset * FLAGS.batch_size:(offset + 1) * FLAGS.batch_size]
  #   # np_x_fixed = np_x_fixed.reshape((test_data.size//FLAGS.batch_size), 116, 1)
  #   # np_x_fixed = (np_x_fixed > 0.5).astype(np.float32)

  for i in range(FLAGS.n_iterations*(n_samples//FLAGS.batch_size)):
    offset = (i)%(n_samples//FLAGS.batch_size)
    # Re-binarize the data at every batch; this improves results
    # Original
    #np_x = arr[offset * FLAGS.batch_size:(offset + 1) * FLAGS.batch_size].reshape(-1,input_dim, 1)
    np_x = arr[offset*FLAGS.batch_size:(offset+1)*FLAGS.batch_size].reshape(-1, input_dim, 1)
    # np_x = np_x.reshape(FLAGS.batch_size, 28, 28, 1)
    # np_x = (np_x > 0.5).astype(np.float32)
    sess.run(train_op, {x: np_x})

    # Print progress and save samples every so often
    t0 = time.time()
    if i % FLAGS.print_every == 0:
      np_elbo, summary_str = sess.run([elbo, summary_op], {x: np_x})
      train_writer.add_summary(summary_str, i)
      print('Iteration: {0:d} ELBO: {1:.3f} Examples/s: {2:.3e}'.format(
          i,
          np_elbo / FLAGS.batch_size,
          FLAGS.batch_size * FLAGS.print_every / (time.time() - t0)))
      t0 = time.time()

      # Save samples
      np_posterior_samples, np_prior_samples = sess.run(
           [posterior_predictive_samples, prior_predictive_samples], {x: np_x})
      # for k in range(FLAGS.n_samples):
      #   f_name = os.path.join(
      #       FLAGS.logdir, 'iter_%d_posterior_predictive_%d_data.jpg' % (i, k))
      #   imsave(f_name, np_x[k, :, :, 0])
      #   f_name = os.path.join(
      #       FLAGS.logdir, 'iter_%d_posterior_predictive_%d_sample.jpg' % (i, k))
      #   imsave(f_name, np_posterior_samples[k, :, :, 0])
      #   f_name = os.path.join(
      #       FLAGS.logdir, 'iter_%d_prior_predictive_%d.jpg' % (i, k))
      #   imsave(f_name, np_prior_samples[k, :, :, 0])

     # Plot the posterior predictive space
     #  if FLAGS.latent_dim == 2:
     #    np_q_mu = sess.run(q_mu, {x: np_x_fixed})
     #    cmap = mpl.colors.ListedColormap(sns.color_palette("husl"))
     #    f, ax = plt.subplots(1, figsize=(6 * 1.1618, 6))
     #    im = ax.scatter(np_q_mu[:, 0], np_q_mu[:, 1], c=np.argmax(labels, 1), cmap=cmap,
     #                alpha=0.7)
     #    ax.set_xlabel('First dimension of sampled latent variable $z_1$')
     #    ax.set_ylabel('Second dimension of sampled latent variable mean $z_2$')
     #    ax.set_xlim([-10., 10.])
     #    ax.set_ylim([-10., 10.])
     #    f.colorbar(im, ax=ax, label='Patient or not')
     #    plt.tight_layout()
     #    plt.savefig(os.path.join(FLAGS.logdir,
     #                             'posterior_predictive_map_frame_%d.png' % i))
     #    plt.close()
     #
     #    nx = ny = 20
     #    x_values = np.linspace(-3, 3, nx)
     #    y_values = np.linspace(-3, 3, ny)
     #    canvas = np.empty((28*ny, 28*nx))
     #    for ii, yi in enumerate(x_values):
     #      for j, xi in enumerate(y_values):
     #        np_z = np.array([[xi, yi]])
     #        x_mean = sess.run(prior_predictive_inp_sample, {z_input: np_z})
     #        canvas[(nx-ii-1)*28:(nx-ii)*28, j*28:(j+1)*28] = x_mean[0].reshape(28, 28)
     #    imsave(os.path.join(FLAGS.logdir,
     #                        'prior_predictive_map_frame_%d.png' % i), canvas)
     #    plt.figure(figsize=(8, 10))
     #    Xi, Yi = np.meshgrid(x_values, y_values)
     #    plt.imshow(canvas, origin="upper")
     #    plt.tight_layout()
     #    plt.savefig()

  # Make the gifs
  # if FLAGS.latent_dim == 2:
  #   os.system(
  #       'convert -delay 15 -loop 0 {0}/posterior_predictive_map_frame*png {0}/posterior_predictive.gif'
  #           .format(FLAGS.logdir))
  #   os.system(
  #       'convert -delay 15 -loop 0 {0}/prior_predictive_map_frame*png {0}/prior_predictive.gif'
  #           .format(FLAGS.logdir))

def main(_):
  if tf.gfile.Exists(FLAGS.logdir):
    tf.gfile.DeleteRecursively(FLAGS.logdir)
  tf.gfile.MakeDirs(FLAGS.logdir)
  train()

if __name__ == '__main__':
  tf.app.run()