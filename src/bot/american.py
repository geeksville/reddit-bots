'''
Created on Apr 28, 2012

@author: kevinh
'''

import reddit
import re
import sys
import locale
import calendar
import time

from time import sleep


class AmericanBot:
    '''Fixes american units in reddit posts'''
    
    myName = "All-American-Bot"
    
    units = {
             #'psi': (6.89475729, 'kPa'),
             
             'mph': (1.609344, 'km/h'),
             
             'gal': (3.78541178, 'L'),
             'gallons': (3.78541178, 'L'),             
                      
             'lbs': (0.45359237, 'kg'),
             
             #'inch': (2.54, 'cm'),
             #'inches': (2.54, 'cm'),       
             'ft': (0.3048, 'm'),      
             'feet': (0.3048, 'm'),             
             'yard': (0.9144, 'm'),
             'mile': (1.609344, 'km'),
             'miles': (1.609344, 'km')                       
             }
    
    uninteresting = set(['dollars', 'dollar', 'hour', 'hours', 'week', 'weeks', 'year', 'years', 'days', 'months', 'million', 'seconds', 'minutes', 'downvotes', 'upvotes'])
 
    # of the form " 4,800 gal" or " 3.8 lbs", "110 lbs" but not "1/2 lbs"
    pattern = re.compile(r"[^/](\d[,\.\d]*) ([a-zA-Z]+)")

    testMessages = ["110 lbs", "I need 10 gallons of milk", "Nearly 1/10 mile." ]
    
    def __init__(self, passwords):
        name = AmericanBot.myName        
        print "Logging in: ", name
        self.r = reddit.Reddit(user_agent=name + ' by /u/punkgeek')
        self.r.login(name, passwords[name])
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        self.lastCommentId = 0
    
    '''Generate a units response message, or None for not interested'''
    def convertUnits(self, msg):
        matches = AmericanBot.pattern.finditer(msg)
        if matches is None:
            return None
        
        conversions = []
        for m in matches:
            amount = m.group(1)
            unit = m.group(2)
            tple = AmericanBot.units.get(unit)            
            try:
                if tple != None:
                    amountf = locale.atof(amount)
                    if amountf >= 6 or amountf > 10000:    # Ignore very large/small values
                        newAmount = amountf * tple[0]
                        newUnit = tple[1]
                        r = '%s %s -> %0.1f %s' % (amount, unit, newAmount, newUnit)
                        conversions.append(r)
                else:
                    if unit not in AmericanBot.uninteresting:
                        #print "  Possible: ", amount, unit
                        pass
            except:
                print "Ignoring:", sys.exc_info()[0]
        
        if not conversions:
            return None
    
        asStr = ", ".join(conversions)
        return "(For our friends outside the USA... %s) - Yeehaw!" % (asStr)
    
    def runTests(self):
        print "Sanity tests:"
        for s in AmericanBot.testMessages:
            print "%s -> %s" % (s, self.convertUnits(s))
            
    def getAllComments(self, comments):
        """Handle resolving MoreComments"""
        result = []
        
        for c in comments:
            if isinstance(c, reddit.objects.Comment):
                result.append(c)
            else:
                extras = c.comments(True)
                result.extend(self.getAllComments(extras))
                
        return result
        
    def makeResponse(self, comment):
        s = str(comment)
        # print "Considering", s
        
        response = self.convertUnits(comment.body)
        if response is None:
            #print "Not interested - skipping"
            return None
        
        myid = self.r.user.name
        if comment.author.name == myid:
            print "Was a post from me - skipping"
            return None
        
        try:
            if myid in (c.author.name for c in self.getAllComments(comment.replies)):
                #print "I've already replied - skipping"
                sys.stdout.write('!') # Show progress
                return None
        except:
            print "Bug while searching comments - skipping"
            return None
        
        return response
    
    def processComment(self, c):
        # Only process simple comments (ingore MoreComments)
        if not isinstance(c, reddit.objects.Comment):
            return
        
        #print "Considering", c.id, c.created_utc
        
        # Ignore low ranking comments (that user may be likely to downvote our response)
        score = c.ups - c.downs
        if score < 1:
            return
        
        # FIXME, ignore by c.created_utc
        resp = self.makeResponse(c)
        if resp != None:
            print "Found match %s" % (c.body)            
            print "Replying %s" % (resp)
            try:
                c.reply(resp)
            except reddit.errors.RateLimitExceeded as detail:
                print detail
                print "We are talking too fast, waiting %f and trying again" % (detail.sleep_time)
                sleep(detail.sleep_time + 5)
                c.reply(resp)
    
    def hasReplied(self, submission):
        """Recurse through all comments - skipping any comments by me"""
        myid = self.r.user.name
        
        for c in submission.comments_flat: 
            if isinstance(c, reddit.objects.Comment):
                if c.author and c.author.name == myid:
                    return True  
                
        return False
                        
    def scanComments(self, comments):
        """Recurse through all comments - skipping any comments by me"""
        myid = self.r.user.name
        
        for c in comments: 
            if isinstance(c, reddit.objects.Comment):
                if c.author and c.author.name == myid:
                    sys.stdout.write('/') # Show progress
                    # print "Was a post from me - skipping all replies"
                else:
                    self.processComment(c)
                    self.scanComments(c.replies)          
                        
    def scanSubmissions(self, submissions):     
        #[str(x) for x in submissions]
        # Only reply to fresh comments, on popular threads
        numdone = 0
        for s in submissions:
            if self.hasReplied(s): # Skip entire article if I've replied even once (FIXME, make optional)
                sys.stdout.write('?')
            else:
                comments = s.comments
                self.scanComments(comments)
                
            # print "*** Submission ", str(s), "(%d top level comments)" % len(comments)
            sys.stdout.write('*') # Show progress
            sys.stdout.flush()
            numdone = numdone + 1
            if numdone % 20 == 0:
                print
                print "Completed:", numdone
            
            sleep(2) # Wait 2 secs per reddit (FIXME, really should wait per comment too)      
          
    def scanAll(self):
        subreddits = ['sneakyfrog', 'politics']
        for subreddit in subreddits:
            submissions = self.r.get_subreddit(subreddit).get_hot(limit=25)
            self.scanSubmissions(submissions)

    # Buggy - misses many comments because reddit comments are being generated too quickly
    def scanRecentComments(self):
        comments = self.r.get_all_comments(limit=500)
        i = 0
        firstCommentId = None
        for c in comments: 
            if isinstance(c, reddit.objects.Comment):
                if i == 0:
                    firstCommentId = c.id
                    
                i = i + 1
                if c.id == self.lastCommentId:
                    print "Reached end of new comments after only %d records" % i
                    break
                
                self.processComment(c)  
                
                sys.stdout.write('.') # Show progress
                sys.stdout.flush()    
                if i % 20 == 0:
                    print
                    print "Completed:", i                
                
        self.lastCommentId = firstCommentId
        
    def scanFrontPage(self):
        self.scanSubmissions(self.r.get_front_page(limit=200))
        
if __name__ == '__main__':
    passwords = eval(open("passwords.dict").read())
    bot = AmericanBot(passwords)
    bot.runTests()
    while True:
        try:
            bot.scanFrontPage()
            #bot.scanRecentComments()
            #sleep(60)
        except:
            print "Restarting scan due to:", sys.exc_info()[0]
        
        print "##### Sleeping #####"
        sleep(5 * 60)
        #bot.scanRecentComments()
        #bot.scanAll()    
