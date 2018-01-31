'''
Model constructed using keras/applications.

Benchmark a Resnet50 model.
'''

from __future__ import print_function

import keras
from keras import applications
from keras.utils import multi_gpu_model

from models import timehistory
from data_generator import generate_img_input_data
if keras.backend.backend() == 'cntk':
  from gpu_mode import cntk_gpu_mode_config, finalize

if keras.backend.backend() == 'tensorflow':
  from tensorflow.contrib.data import Dataset

class Resnet50Benchmark:

  def __init__(self):
    self.test_name = "resnet50"
    self.sample_type = "images"
    self.total_time = 0
    self.batch_size = 64
    self.epochs = 4
    self.num_samples = 1000
    self.test_type = 'channels_first, batchnorm, learning_phase, batch_size'

  def run_benchmark(self, gpus=0):
    print("Running model ", self.test_name)

    input_shape = (self.num_samples, 3, 224, 224)
    num_classes = 1000

    x_train, y_train = generate_img_input_data(input_shape, num_classes)

    if keras.backend.backend == "tensorflow" and gpus > 1:
      keras.backend.set_image_data_format('channels_first')

    keras.backend.set_learning_phase(True)

    resnet_model = applications.ResNet50(weights=None)

    y_train = keras.utils.to_categorical(y_train, num_classes)

    if keras.backend.image_data_format() == 'channels_last':
      x_train = x_train.transpose(0, 2, 3, 1)

    x_train = x_train.astype('float32')
    x_train /= 255

    # Create the dataset and its associated one-shot iterator.
    dataset = Dataset.from_tensor_slices((x_train, y_train))
    dataset = dataset.repeat()
    dataset = dataset.shuffle(10000)
    dataset = dataset.batch(self.batch_size)
    iterator = dataset.make_one_shot_iterator()

    # Model creation using tensors from the get_next() graph node.
    inputs, targets = iterator.get_next()
    model_input = keras.layers.Input(tensor=inputs)
    model_output = resnet_model(model_input)
    model = keras.models.Model(inputs=model_input, outputs=model_output)


    opt = keras.optimizers.rmsprop(lr=0.0001, decay=1e-6)

    if keras.backend.backend() == "tensorflow" and gpus > 1:
      model = multi_gpu_model(model, gpus=gpus)

    # model.compile(loss='categorical_crossentropy',
    #               optimizer=opt,
    #               metrics=['accuracy'])
    model.compile(optimizer=keras.optimizers.RMSprop(lr=2e-3, decay=1e-5),
                  loss='categorical_crossentropy',
                  metrics=['accuracy'],
                  target_tensors=[targets])

    # create a distributed trainer for cntk
    if keras.backend.backend() == "cntk" and gpus > 1:
      start, end = cntk_gpu_mode_config(model, x_train.shape[0])
      x_train = x_train[start: end]
      y_train = y_train[start: end]

    time_callback = timehistory.TimeHistory()

    # model.fit(x_train,
    #                     y_train,
    #                     batch_size=self.batch_size,
    #                     epochs=self.epochs,
    #                     shuffle=True,
    #                     callbacks=[time_callback])
    model.fit(epochs=self.epochs,
                    steps_per_epoch=10)

    self.total_time = 0
    for i in range(1, self.epochs):
      self.total_time += time_callback.times[i]

    if keras.backend.backend() == "tensorflow":
      keras.backend.clear_session()

    if keras.backend.backend() == "cntk" and gpus > 1:
      finalize()

