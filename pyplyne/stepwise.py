import traceback
import logging
logger = logging.getLogger("stepwise")

class StepwiseException(Exception):
    default_message = "Stepwise failed"
    def __init__(self, message = None, underlying = None):
        Exception.__init__(self)
        self.message = message or self.default_message
        self.underlying = underlying

    def __str__(self):
        if self.underlying:
            return super(StepwiseException, self).__str__() + "%s. Underlying Error: %s" % (self.message, self.underlying)
        return super(StepwiseException, self).__str__() + "%s" % self.message

class StepwiseAborted(StepwiseException):
    default_message = "Stepwise aborted by user"
    pass

class StepwiseStepFailed(StepwiseException):
    default_message = "Stepwise step failed"
    pass

class StepwiseStepSkipped(StepwiseException):
    pass

class StepwiseStepSkippedByUser(StepwiseStepSkipped):
    pass
    
class StepwiseStepSkippedForTesting(StepwiseStepSkipped):
    pass


class StepWise:
    def __init__(self, taskname = "task", stepwise = False, test = False, items = None, parent = None):
        self.stepwise = stepwise
        self.test = test
        self.taskname = taskname
        self.items = items or self
        self.parent = parent
        
    def __enter__(self):
        if self.stepwise:
            answer = raw_input("%sNext Step: %s. Proceed? ( Y/n/s(kip) ) " % ( "TEST! " if self.test else "", self.taskname))
            if answer.lower().startswith("s"):
                raise StepwiseStepSkippedByUser()
            if answer.lower().startswith("n"):
                raise StepwiseAborted()
        if self.test:
            raise StepwiseStepSkippedForTesting()
        return self

    def __exit__(self, type, value, traceback):
        if isinstance(value, Exception):
            if isinstance(value, StepwiseStepSkipped):
                logger.info("Task %s was skipped", self.taskname)
            if isinstance(value, StepwiseAborted):
                logger.info("User aborted at task %s", self.taskname)
            else:
                logger.exception("Task %s failed", self.fullname)
            answer = raw_input("\nProceed? ( y/N ) " )
            if not answer.lower().startswith("y"):
                if not isinstance(value, StepwiseException):
                    e = StepwiseException(underlying = value)
                    raise e
            return True # no exception
        
    def forall(self, items, callback ):
        try:
            with self:
                for i,item in enumerate(items):
                    try:
                        with self.subtask("%d"):
                            callback(item)
                    except StepwiseStepSkipped:
                        continue
        except StepwiseStepSkipped:
            pass

    def iterate(self, items):
        with self:
            for i,item in enumerate(items):
                try:
                    with StepWise("%s-%d" % (self.taskname, i), self.stepwise, self.test ):
                        print "yielding ", item
                        yield item
                except StepwiseStepSkipped:
                    continue
                except StepwiseAborted:
                    break

    def __iter__(self):
        with self:
            for i,item in enumerate(self.items):
                try:
                    with StepWise("%s-%d" % (self.taskname, i), self.stepwise, self.test):
                        print "yielding ", item
                        yield item
                except StepwiseStepSkipped:
                    logger.info("Guarded task was skipped")
                    continue
                except StepwiseAborted:
                    logger.info("Guarded task was aborted")
                    break
            
    @classmethod
    def Items(cls, items):
        return cls.GuardedItems(items)

    def items(self, items):
        self.items = items
        return self

    class GuardedItems:
        def __init__(self, items):
            self.items = items

        def __enter__(self):
            return self.items

        def __exit__(self, type, value, traceback):
            if isinstance(value, StepwiseStepSkipped):
                logger.info("Guarded task was skipped")
                return True
            if isinstance(value, StepwiseAborted):
                logger.error("Guarded task was aborted")
                return True
            if isinstance(value,(StepwiseStepFailed, StepwiseException)):
                logger.error("Guarded task failed")
                return True 
        
            
    def subtask(self, name, stepwise = None, test = None):
        return StepWise(name,
                        stepwise = self.stepwise if stepwise is None else stepwise,
                        test = self.test if test is None else test,
                        parent = self)

    @property
    def fullname(self):
        names = []
        p = self
        while p is not None:
            names.append(p.taskname)
            p = p.parent
        return ".".join(names)

class guard:
    def __enter__(self):
        pass
    def __exit__(self, type, value, traceback):
        if isinstance(value, StepwiseStepSkipped):
            logger.info("Guarded task was skipped")
            return True
        if isinstance(value, StepwiseAborted):
            logger.error("Guarded task was aborted")
            return True
        if isinstance(value,(StepwiseStepFailed, StepwiseException)):
            logger.error("Guarded task failed")
            return True 

class GuardedItems:
    def __init__(self, items):
        self.items = items

    def __enter__(self):
        return self.items

    def __exit__(self, type, value, traceback):
        if isinstance(value, StepwiseStepSkipped):
            logger.info("Guarded task was skipped")
            return True
        if isinstance(value, StepwiseAborted):
            logger.error("Guarded task was aborted")
            return True
        if isinstance(value,(StepwiseStepFailed, StepwiseException)):
            logger.error("Guarded task failed")
            return True 


class Step:
    def __init__(self, taskname = "task", stepwise = False, test = False, parent = None):
        self.stepwise = stepwise
        self.test = test
        self.taskname = taskname
        self.parent = parent
        
    def __enter__(self):
        if self.stepwise:
            answer = raw_input("%sNext Step: %s. Proceed? ( Yes/no/skip ) " % ( "TEST! " if self.test else "", self.taskname))
            if answer.lower().startswith("s"):
                raise StepwiseStepSkippedByUser()
            if answer.lower().startswith("n"):
                raise StepwiseAborted()
        if self.test:
            raise StepwiseStepSkippedForTesting()
        return self

    def __exit__(self, type, value, traceback):
        if isinstance(value, Exception):
            logger.exception("Task %s failed", self.fullname)
            answer = raw_input("\nProceed with next step? ( yes/No ) " )
            if not answer.lower().startswith("y"):
                if not isinstance(value, StepwiseException):
                    e = StepwiseException(underlying = value)
                    e.traceback = traceback
                    raise e
            return True # no exception
        
    def forall(self, items, callback ):
        try:
            with self:
                for i,item in enumerate(items):
                    try:
                        with self.Substep("%d" % i):
                            callback(item)
                    except StepwiseStepSkipped:
                        continue
        except StepwiseStepSkipped:
            pass


    def Substep(self, name, stepwise = None, test = None):
        return Step(name,
                    stepwise = self.stepwise if stepwise is None else stepwise,
                    test = self.test if test is None else test,
                    parent = self)

    @property
    def fullname(self):
        names = []
        p = self
        while p is not None:
            names.append(p.taskname)
            p = p.parent
        return ".".join(names)

class Stepper:
    def __init__(self, items):
        self.items = items

    def __enter__(self):
        return self.items

    def __exit__(self, type, value, traceback):
        if isinstance(value, StepwiseStepSkipped):
            logger.info("Guarded task was skipped")
            return True
        if isinstance(value, StepwiseAborted):
            logger.error("Guarded task was aborted")
            return True
        if isinstance(value,(StepwiseStepFailed, StepwiseException)):
            logger.error("Guarded task failed")
            return True 

if __name__ == "__main__":
    logging.basicConfig(level = logging.DEBUG)

    def cb(a):
        if a==6:
            raise KeyError
        print a
        
    Step("loop1", True ).forall(range(10), cb)

   
    with Step("loop2", True) as step:
        for item in range(10):
            with step.Substep("%d" % item, test = (item == 4)):
                if item == 6:
                    raise KeyError()
                print item
            print "loop2", item

    for a in StepWise("loop3", True).iterate(range(10)):
        if a==6:
            raise KeyError
        print "loop3", a

