# -*- coding: utf-8 -*-
#
# redisbayes - Naïve Bayesian Text Classifier on Redis
# Copyright (c) 2012 Justine Alexandra Roberts Tunney
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
ur"""

    redisbayes
    ~~~~~~~~~~

    Naïve Bayesian Text Classifier on Redis.

    I wrote this to filter spammy comments from a high traffic forum website
    and it worked pretty well.  It can work for you too :)

    For example::

        >>> import redis
        >>> import redisbayes
        >>> rb = redisbayes.RedisBayes(redis.Redis(), prefix='bayes:test:')
        >>> rb.flush()
        >>> rb.classify('nothing trained yet') is None
        True
        >>> rb.train('good', 'sunshine drugs love sex lobster sloth')
        >>> rb.train('bad', 'fear death horror government zombie god')
        >>> rb.classify('sloths are so cute i love them')
        'good'
        >>> rb.classify('i fear god and love the government')
        'bad'
        >>> int(rb.score('i fear god and love the government')['bad'])
        -9
        >>> int(rb.score('i fear god and love the government')['good'])
        -14
        >>> rb.untrain('good', 'sunshine drugs love sex lobster sloth')
        >>> rb.untrain('bad', 'fear death horror government zombie god')
        >>> rb.score('lolcat')
        {}

    Words are lowercased and unicode is supported::

        >>> print english_tokenizer("Æther")[0]
        æther

    Common english words and 1-2 character words are ignored::

        >>> english_tokenizer("greetings mary a b aa bb")
        [u'mary']

    Some characters are removed::

        >>> print english_tokenizer("contraction's")[0]
        contraction's
        >>> print english_tokenizer("what|is|goth")[0]
        goth

"""

import re
import math


__version__ = '0.1.1'

english_ignore = set("""
a able about above abroad according accordingly across actually adj after
afterwards again against ago ahead ain't all allow allows almost alone along
alongside already also although always am amid amidst among amongst an and
another any anybody anyhow anyone anything anyway anyways anywhere apart
appear appreciate appropriate are aren't around as a's aside ask asking
associated at available away awfully b back backward backwards be became
because become becomes becoming been before beforehand begin behind being
believe below beside besides best better between beyond both brief but by c
came can cannot cant can't caption cause causes certain certainly changes
clearly c'mon co co. com come comes concerning consequently consider
considering contain containing contains corresponding could couldn't course
c's currently d dare daren't definitely described despite did didn't different
directly do does doesn't doing done don't down downwards during e each edu eg
eight eighty either else elsewhere end ending enough entirely especially et
etc even ever evermore every everybody everyone everything everywhere ex
exactly example except f fairly far farther few fewer fifth first five
followed following follows for forever former formerly forth forward found
four from further furthermore g get gets getting given gives go goes going
gone got gotten greetings h had hadn't half happens hardly has hasn't have
haven't having he he'd he'll hello help hence her here hereafter hereby herein
here's hereupon hers herself he's hi him himself his hither hopefully how
howbeit however hundred i i'd ie if ignored i'll i'm immediate in inasmuch inc
inc. indeed indicate indicated indicates inner inside insofar instead into
inward is isn't it it'd it'll its it's itself i've j just k keep keeps kept
know known knows l last lately later latter latterly least less lest let let's
like liked likely likewise little look looking looks low lower ltd m made
mainly make makes many may maybe mayn't me mean meantime meanwhile merely
might mightn't mine minus miss more moreover most mostly mr mrs much must
mustn't my myself n name namely nd near nearly necessary need needn't needs
neither never neverf neverless nevertheless new next nine ninety no nobody non
none nonetheless noone no-one nor normally not nothing notwithstanding novel
now nowhere o obviously of off often oh ok okay old on once one ones one's
only onto opposite or other others otherwise ought oughtn't our ours ourselves
out outside over overall own p particular particularly past per perhaps placed
please plus possible presumably probably provided provides q que quite qv r
rather rd re really reasonably recent recently regarding regardless regards
relatively respectively right round s said same saw say saying says second
secondly see seeing seem seemed seeming seems seen self selves sensible sent
serious seriously seven several shall shan't she she'd she'll she's should
shouldn't since six so some somebody someday somehow someone something
sometime sometimes somewhat somewhere soon sorry specified specify specifying
still sub such sup sure t take taken taking tell tends th than thank thanks
thanx that that'll thats that's that've the their theirs them themselves then
thence there thereafter thereby there'd therefore therein there'll there're
theres there's thereupon there've these they they'd they'll they're they've
thing things think third thirty this thorough thoroughly those though three
through throughout thru thus till to together too took toward towards tried
tries truly try trying t's twice two u un under underneath undoing
unfortunately unless unlike unlikely until unto up upon upwards us use used
useful uses using usually v value various versus very via viz vs w want wants
was wasn't way we we'd welcome well we'll went were we're weren't we've what
whatever what'll what's what've when whence whenever where whereafter whereas
whereby wherein where's whereupon wherever whether which whichever while
whilst whither who who'd whoever whole who'll whom whomever who's whose why
will willing wish with within without wonder won't would wouldn't x y yes yet
you you'd you'll your you're yours yourself yourselves you've z zero
successful greatest began including being all for close but
""".split())


def tidy(text):
    if not isinstance(text, basestring):
        text = str(text)
    if not isinstance(text, unicode):
        text = text.decode('utf8')
    text = text.lower()
    return re.sub(r'[\_.,<>:;~+|\[\]?`"!@#$%^&*()\s]', ' ', text, re.UNICODE)


def english_tokenizer(text):
    words = tidy(text).split()
    return [w for w in words if len(w) > 2 and w not in english_ignore]


def occurances(words):
    counts = {}
    for word in words:
        if word in counts:
            counts[word] += 1
        else:
            counts[word] = 1
    return counts


class RedisBayes(object):
    def __init__(self, redis=None, prefix='bayes:', correction=0.1,
                 tokenizer=None):
        self.redis = redis
        self.prefix = prefix
        self.correction = correction
        self.tokenizer = tokenizer or english_tokenizer
        if not self.redis:
            import redis
            redis = redis.Redis()

    def flush(self):
        for cat in self.redis.smembers(self.prefix + 'categories'):
            self.redis.delete(self.prefix + cat)
        self.redis.delete(self.prefix + 'categories')

    def train(self, category, text):
        self.redis.sadd(self.prefix + 'categories', category)
        for word, count in occurances(self.tokenizer(text)).iteritems():
            self.redis.hincrby(self.prefix + category, word, count)

    def untrain(self, category, text):
        for word, count in occurances(self.tokenizer(text)).iteritems():
            cur = self.redis.hget(self.prefix + category, word)
            if cur:
                new = int(cur) - count
                if new > 0:
                    self.redis.hset(self.prefix + category, word, new)
                else:
                    self.redis.hdel(self.prefix + category, word)
        if self.tally(category) == 0:
            self.redis.delete(self.prefix + category)
            self.redis.srem(self.prefix + 'categories', category)

    def classify(self, text):
        score = self.score(text)
        if not score:
            return None
        return sorted(score.iteritems(), key=lambda v: v[1])[-1][0]

    def score(self, text):
        occurs = occurances(self.tokenizer(text))
        scores = {}
        for category in self.redis.smembers(self.prefix + 'categories'):
            tally = self.tally(category)
            scores[category] = 0.0
            for word, count in occurs.iteritems():
                score = self.redis.hget(self.prefix + category, word)
                assert not score or score > 0, "corrupt bayesian database"
                score = score or self.correction
                scores[category] += math.log(float(score) / tally)
        return scores

    def tally(self, category):
        tally = sum(int(x) for x in self.redis.hvals(self.prefix + category))
        assert tally >= 0, "corrupt bayesian database"
        return tally


if __name__ == '__main__':
    import doctest
    doctest.testmod()
