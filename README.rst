.. -*-rst-*-

============
 redisbayes
============

:name:        redisbayes
:description: Naïve Bayesian Text Classifier on Redis
:copyright:   © 2012 Justine Alexandra Roberts Tunney
:license:     MIT


What Is This?
=============

It's a spam filter.  I wrote this to filter spammy comments from a high
traffic forum website and it worked pretty well.  It can work for you too :)
It's not tied to any particular format like email, it just deals with the raw
text.

This is probably the only spam filtering library you'll find for Python that's
simple (170 lines of code), works (30 lines of test code), and doesn't suck.


Installation
============

From folder::

    sudo python setup.py install

From cheeseshop::

    sudo pip install redisbayes

From git::

    sudo pip install git+git://github.com/jart/redisbayes.git


Basic Usage
===========

::

    import redis, redisbayes
    rb = redisbayes.RedisBayes(redis=redis.Redis())

    rb.train('good', 'sunshine drugs love sex lobster sloth')
    rb.train('bad', 'fear death horror government zombie god')

    assert rb.classify('sloths are so cute i love them') == 'good'
    assert rb.classify('i fear god and love the government') == 'bad'

    print rb.score('i fear god and love the government')

    rb.untrain('good', 'sunshine drugs love sex lobster sloth')
    rb.untrain('bad', 'fear death horror government zombie god')
