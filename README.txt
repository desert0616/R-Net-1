Environment Setup:

The training part depends on cuda and cudnn so that a proper cuda environment is required. We use cuda 9.0 with cudnn 7.0.4. Such version should be ok for this project.

The python scripts depend on several libraries as follows:

tensorflow tqdm spacy nltk cython jnius

Since the cudnn-gru is required, so you may need to install tensorflow-gpu (with cuda support) for tensorflow.

The preprocessing introduces Stanford-NER, which is a Java library. So we need jnius, a python-java bridge, which uses JNI protocol.

However, the latest release jnius has bugs related to string encoding on Python3, which means that we have to build it from the source code.

Here are the instructions:

1. git clone https://github.com/kivy/pyjnius.git
2. The build needs ant, you can install it via "sudo apt-get install ant" if you are in Ubuntu, or "brew install ant" if you are on Mac OS X.
3. The build depends on cpython, so you have to “pip3 install cython” in advance.
4. make PYTHON3=1
5. python3 setup.py build
6. python3 setup.py install

Meanwhile, jnius needs JAVA_HOME env. So it is required to pass such env variable in advance, e.g., export JAVA_HOME="$YOUR JAVA HOME PATH$".

The latest Stanford-NER needs JDK 1.8, the java_home may be located at "/usr/lib/jvm/java-8-openjdk-amd64/" if you are in Ubuntu, or "/Library/Java/JavaVirtualMachines/jdk1.8.0_162.jdk/Contents/Home'" if you are in Mac OS X.


Running:

0. You need to download datasets and pre-trained files via “sh download.sh”. It will put data in your home folder. So that you only need to execute it once (If you have done it on other kinds of experiment, you can skip this step).
1. Embedding combination experiment will introduce other kinds of features compared with the original so that it is required to do a fresh preprocessing via “python3 config.py --mode prepro”.
2. Word embedding is necessary, and you can switch other features in the config.py file. In line 101, you can find 4 switchers accordingly. (You need NOT to re-preprocessing if you only modify the switchers.)
3. To train the model via given configuration, execute “python3 config.py --mode train”. It will take about 8 hours on GTX 1080Ti.
4. To fetch the performance, execute “python3 config.py --mode test”.


Backup:

You can also get the source code via https://github.com/desert0616/R-Net-1/.