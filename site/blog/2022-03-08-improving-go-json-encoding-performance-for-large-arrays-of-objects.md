{% extends "blog/layout.tmpl" %}

{% block postTitle %}Improving Go's encoding/json encoder performance for large arrays of objects{% endblock %}
{% block postDate %}March 3, 2022{% endblock %}
{% block postAuthor %}Phil Eaton{% endblock %}
{% block postAuthorEmail %}phil@multiprocess.io{% endblock %}
{% block postTags %}go,json{% endblock %}

{% block postBody %}
I was looking into some of
[octosql](https://github.com/cube2222/octosql)'s benchmarks the other
day and noticed a large chunk of time in
[DataStation](https://github.com/multiprocessio/datastation)/[dsq](https://github.com/multiprocessio/dsq)
is spent in encoding JSON objects. JSON is an intermediate format in
DataStation and it's pretty inefficient. But the reason it's used is
because almost every scripting language supported by DataStation has a
builtin library for reading/writing JSON.

## Useful datasets

I threw together a quick CLI for generating fake data,
[fakegen](https://github.com/multiprocessio/fakegen). And generated
two datasets: one with 20 columns and 1M rows, and one with 1K columns
and 10K rows.

```bash
$ mkdir -p ~/tmp/benchmarks && cd ~/tmp/benchmarks
$ go install github.com/multiprocessio/fakegen@latest
$ fakegen --rows 100000 --cols 20 > long.json
$ fakegen --rows 10000 --cols 1000 > wide.json
$ ls -lah *.json
-rw-r--r-- 1 phil phil 1.2G Mar  3 15:42 long.json
-rw-r--r-- 1 phil phil 1.6G Mar  3 15:44 wide.json
$ wc *.json
wc *.json
   1999999  114514109 1214486728 long.json
     19999  213613856 1666306735 wide.json
```

## A benchmark program

Then I started looking into what Go's JSON encoder is actually
spending time doing.

First I wrote a program that reads and decodes a JSON file, picks an
encoder (just the standard library encoder for now), and encodes the
JSON object back into another file. I used
[pkg/profile](https://github.com/pkg/profile) to simplify the process
of hooking into pprof so that I could get a CPU profile of execution.

```go
$ go mod init main
$ cat main.go
package main

import (
        "encoding/json"
        "os"

        "github.com/pkg/profile"
)

func stdlibEncoder(out *os.File, obj interface{}) error {
        encoder := json.NewEncoder(out)
        return encoder.Encode(obj)
}

func main() {
        var in string
        encoderArg := "stdlib"
        encoder := stdlibEncoder

        for i, arg := range os.Args {
                if arg == "--in" {
                        in = os.Args[i+1]
                        i += 1
                        continue
                }

                if arg == "--encoder" {
                        encoderArg = os.Args[i+1]
                        switch encoderArg {
                        case "stdlib":
                                encoder = stdlibEncoder
                        default:
                                panic("Unknown encoder: " + encoderArg)
                        }
                        i += 1
                        continue
                }
        }

        fr, err := os.Open(in + ".json")
        if err != nil {
                panic(err)
        }
        defer fr.Close()

        decoder := json.NewDecoder(fr)
        var o interface{}
        err = decoder.Decode(&o)
        if err != nil {
                panic(err)
        }

        fw, err := os.OpenFile(in+"-"+encoderArg+".json", os.O_TRUNC|os.O_WRONLY|os.O_CREATE, os.ModePerm)
        if err != nil {
                panic(err)
        }
        defer fw.Close()

        p := profile.Start()
        defer p.Stop()
        err = encoder(fw, o)
        if err != nil {
                panic(err)
        }
}
```

Compile and run it:

```bash
$ go mod tidy
$ go build -o main main.go
$ ./main --in long
2022/03/03 15:49:00 profile: cpu profiling enabled, /tmp/profile2956118756/cpu.pprof
2022/03/03 15:49:08 profile: cpu profiling disabled, /tmp/profile2956118756/cpu.pprof
```

## Examining pprof results

Now we can run `go tool pprof` against this profile to see where we're
spending the most time:

```
$ go tool pprof -top /tmp/profile2956118756/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 3:49pm (UTC)
Duration: 8.15s, Total samples = 9.66s (118.54%)
Showing nodes accounting for 8.75s, 90.58% of 9.66s total
Dropped 95 nodes (cum <= 0.05s)
      flat  flat%   sum%        cum   cum%
     1.06s 10.97% 10.97%      1.55s 16.05%  encoding/json.(*encodeState).string
     0.57s  5.90% 16.87%      1.85s 19.15%  runtime.scanobject
     0.55s  5.69% 22.57%      0.55s  5.69%  runtime.memmove
     0.51s  5.28% 27.85%      0.51s  5.28%  cmpbody
     0.42s  4.35% 32.19%      1.53s 15.84%  runtime.mallocgc
     0.33s  3.42% 35.61%      0.33s  3.42%  runtime.pageIndexOf (inline)
     0.25s  2.59% 38.20%      0.40s  4.14%  runtime.findObject
     0.24s  2.48% 40.68%      0.33s  3.42%  runtime.heapBitsSetType
     0.21s  2.17% 42.86%      0.71s  7.35%  runtime.greyobject
     0.21s  2.17% 45.03%      0.33s  3.42%  runtime.mapiternext
     0.21s  2.17% 47.20%      0.85s  8.80%  sort.insertionSort_func
     0.20s  2.07% 49.28%      0.20s  2.07%  strconv.ryuDigits32
     0.19s  1.97% 51.24%      7.59s 78.57%  encoding/json.mapEncoder.encode
     0.19s  1.97% 53.21%      0.74s  7.66%  sort.doPivot_func
     0.18s  1.86% 55.07%      0.70s  7.25%  encoding/json.mapEncoder.encode.func1
     0.17s  1.76% 56.83%      0.17s  1.76%  runtime.nextFreeFast (inline)
     0.16s  1.66% 58.49%      0.48s  4.97%  runtime.typedmemmove
     0.14s  1.45% 59.94%      0.14s  1.45%  runtime.memclrNoHeapPointers
     0.13s  1.35% 61.28%      7.66s 79.30%  encoding/json.(*encodeState).reflectValue
     0.13s  1.35% 62.63%      0.35s  3.62%  strconv.ryuDigits
     0.12s  1.24% 63.87%      0.12s  1.24%  bytes.(*Buffer).tryGrowByReslice (partial-inline)
     0.11s  1.14% 65.01%      0.43s  4.45%  bytes.(*Buffer).WriteString
     0.10s  1.04% 66.05%      0.50s  5.18%  internal/reflectlite.Swapper.func9
     0.10s  1.04% 67.08%      0.39s  4.04%  internal/reflectlite.typedmemmove
     0.10s  1.04% 68.12%      0.10s  1.04%  runtime.procyield
     0.10s  1.04% 69.15%      0.56s  5.80%  strconv.genericFtoa
     0.09s  0.93% 70.08%      0.49s  5.07%  reflect.(*MapIter).Next
     0.09s  0.93% 71.01%      0.09s  0.93%  runtime.heapBits.bits (inline)
     0.09s  0.93% 71.95%      0.37s  3.83%  runtime.mapaccess2
     0.08s  0.83% 72.77%      0.13s  1.35%  bytes.(*Buffer).WriteByte
     0.08s  0.83% 73.60%      1.12s 11.59%  reflect.copyVal
     0.08s  0.83% 74.43%      0.09s  0.93%  runtime.heapBitsForAddr (inline)
     0.07s  0.72% 75.16%      0.57s  5.90%  encoding/json.valueEncoder
     0.07s  0.72% 75.88%      0.56s  5.80%  reflect.(*MapIter).Key
     0.07s  0.72% 76.60%      0.07s  0.72%  runtime.(*mspan).divideByElemSize (inline)
     0.07s  0.72% 77.33%      0.07s  0.72%  runtime.add (partial-inline)
     0.07s  0.72% 78.05%      0.07s  0.72%  runtime.heapBits.next (inline)
     0.07s  0.72% 78.78%      0.07s  0.72%  runtime.memhash64
     0.06s  0.62% 79.40%      0.69s  7.14%  encoding/json.floatEncoder.encode
     0.06s  0.62% 80.02%      0.80s  8.28%  reflect.unsafe_New
     0.06s  0.62% 80.64%      0.10s  1.04%  runtime.(*bmap).overflow (inline)
     0.06s  0.62% 81.26%      0.09s  0.93%  runtime.(*gcBits).bitp (inline)
     0.06s  0.62% 81.88%      0.18s  1.86%  runtime.nilinterhash
     0.06s  0.62% 82.51%      0.07s  0.72%  runtime.spanOf (inline)
     0.06s  0.62% 83.13%      0.18s  1.86%  sort.medianOfThree_func
     0.05s  0.52% 83.64%      1.16s 12.01%  encoding/json.stringEncoder
     0.05s  0.52% 84.16%      0.53s  5.49%  reflect.typedmemmove (partial-inline)
     0.05s  0.52% 84.68%      0.05s  0.52%  runtime.(*gcWork).putFast (inline)
     0.05s  0.52% 85.20%      0.05s  0.52%  runtime.acquirem (inline)
     0.05s  0.52% 85.71%      1.86s 19.25%  runtime.gcDrain
     0.05s  0.52% 86.23%      0.08s  0.83%  runtime.nilinterequal
     0.05s  0.52% 86.75%      1.71s 17.70%  sort.quickSort_func
     0.04s  0.41% 87.16%      0.11s  1.14%  runtime.typehash
     0.04s  0.41% 87.58%      0.39s  4.04%  strconv.ryuFtoaShortest
     0.04s  0.41% 87.99%      0.46s  4.76%  sync.(*Map).Load
     0.03s  0.31% 88.30%      7.66s 79.30%  encoding/json.interfaceEncoder
     0.03s  0.31% 88.61%      0.70s  7.25%  reflect.(*MapIter).Value
     0.03s  0.31% 88.92%      0.09s  0.93%  reflect.Value.Elem
     0.03s  0.31% 89.23%      0.06s  0.62%  strconv.formatDigits
     0.02s  0.21% 89.44%      0.05s  0.52%  bytes.(*Buffer).Write
     0.02s  0.21% 89.65%      0.48s  4.97%  encoding/json.typeEncoder
     0.02s  0.21% 89.86%      0.23s  2.38%  runtime.(*mheap).alloc
     0.02s  0.21% 90.06%      0.11s  1.14%  runtime.(*mheap).allocSpan
     0.01s   0.1% 90.17%      0.08s  0.83%  reflect.mapiterinit
     0.01s   0.1% 90.27%      0.31s  3.21%  reflect.mapiternext
     0.01s   0.1% 90.37%      0.29s  3.00%  runtime.(*mcache).nextFree
     0.01s   0.1% 90.48%      0.15s  1.55%  runtime.newobject
     0.01s   0.1% 90.58%      0.08s  0.83%  runtime.sweepone
```

Roughly 8.2 seconds. Now let's also run against the wide JSON dataset
and profile that result.

```
$ ./main --in wide
2022/03/03 15:50:30 profile: cpu profiling enabled, /tmp/profile800187419/cpu.pprof
2022/03/03 15:50:36 profile: cpu profiling disabled, /tmp/profile800187419/cpu.pprof
$ go tool pprof -top /tmp/profile800187419/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 3:50pm (UTC)
Duration: 6.36s, Total samples = 7.11s (111.88%)
Showing nodes accounting for 6.67s, 93.81% of 7.11s total
Dropped 61 nodes (cum <= 0.04s)
      flat  flat%   sum%        cum   cum%
     1.28s 18.00% 18.00%      1.75s 24.61%  encoding/json.(*encodeState).string
     0.77s 10.83% 28.83%      0.77s 10.83%  cmpbody
     0.41s  5.77% 34.60%      0.41s  5.77%  runtime.memmove
     0.34s  4.78% 39.38%      1.15s 16.17%  encoding/json.mapEncoder.encode.func1
     0.32s  4.50% 43.88%      1.05s 14.77%  runtime.scanobject
     0.29s  4.08% 47.96%      1.53s 21.52%  sort.doPivot_func
     0.26s  3.66% 51.62%      0.68s  9.56%  runtime.mallocgc
     0.26s  3.66% 55.27%      0.26s  3.66%  runtime.procyield
     0.17s  2.39% 57.67%      0.38s  5.34%  runtime.greyobject
     0.17s  2.39% 60.06%      0.17s  2.39%  runtime.pageIndexOf (inline)
     0.15s  2.11% 62.17%      0.22s  3.09%  runtime.findObject
     0.15s  2.11% 64.28%      0.28s  3.94%  runtime.typedmemmove
     0.13s  1.83% 66.10%      5.80s 81.58%  encoding/json.mapEncoder.encode
     0.12s  1.69% 67.79%      0.48s  6.75%  sort.insertionSort_func
     0.10s  1.41% 69.20%      0.29s  4.08%  internal/reflectlite.typedmemmove
     0.10s  1.41% 70.60%      0.10s  1.41%  runtime.memclrNoHeapPointers
     0.09s  1.27% 71.87%      0.45s  6.33%  internal/reflectlite.Swapper.func9
     0.09s  1.27% 73.14%      0.36s  5.06%  reflect.(*MapIter).Key
     0.09s  1.27% 74.40%      0.09s  1.27%  runtime.heapBits.bits (inline)
     0.09s  1.27% 75.67%      0.12s  1.69%  runtime.heapBitsSetType
     0.08s  1.13% 76.79%      0.12s  1.69%  bytes.(*Buffer).WriteByte
     0.08s  1.13% 77.92%      0.08s  1.13%  runtime.nextFreeFast (inline)
     0.07s  0.98% 78.90%      0.17s  2.39%  runtime.mapaccess2
     0.06s  0.84% 79.75%      0.11s  1.55%  runtime.mapiternext
     0.06s  0.84% 80.59%      0.06s  0.84%  strconv.ryuDigits32
     0.06s  0.84% 81.43%      0.25s  3.52%  sync.(*Map).Load
     0.05s   0.7% 82.14%      0.41s  5.77%  bytes.(*Buffer).WriteString
     0.05s   0.7% 82.84%      0.07s  0.98%  internal/reflectlite.arrayAt (inline)
     0.05s   0.7% 83.54%      0.18s  2.53%  reflect.(*MapIter).Next
     0.05s   0.7% 84.25%      0.05s   0.7%  runtime.add (partial-inline)
     0.05s   0.7% 84.95%      0.05s   0.7%  runtime.memhash64
     0.05s   0.7% 85.65%      0.05s   0.7%  runtime.spanOf (inline)
     0.05s   0.7% 86.36%      0.13s  1.83%  strconv.ryuDigits
     0.04s  0.56% 86.92%      0.04s  0.56%  bytes.(*Buffer).tryGrowByReslice (inline)
     0.04s  0.56% 87.48%      5.80s 81.58%  encoding/json.(*encodeState).reflectValue
     0.04s  0.56% 88.05%      0.04s  0.56%  reflect.Value.IsNil (inline)
     0.04s  0.56% 88.61%      0.04s  0.56%  runtime.cmpstring
     0.04s  0.56% 89.17%      0.12s  1.69%  sort.medianOfThree_func
     0.04s  0.56% 89.73%      2.09s 29.40%  sort.quickSort_func
     0.04s  0.56% 90.30%      0.21s  2.95%  strconv.genericFtoa
     0.03s  0.42% 90.72%      0.28s  3.94%  encoding/json.typeEncoder
     0.03s  0.42% 91.14%      0.36s  5.06%  reflect.(*MapIter).Value
     0.03s  0.42% 91.56%      1.26s 17.72%  runtime.gcDrain
     0.03s  0.42% 91.98%      0.04s  0.56%  runtime.heapBits.next (inline)
     0.02s  0.28% 92.26%      0.26s  3.66%  encoding/json.floatEncoder.encode
     0.02s  0.28% 92.55%      5.80s 81.58%  encoding/json.interfaceEncoder
     0.02s  0.28% 92.83%      0.06s  0.84%  reflect.Value.Elem
     0.02s  0.28% 93.11%      0.60s  8.44%  reflect.copyVal
     0.01s  0.14% 93.25%      0.12s  1.69%  reflect.mapiternext
     0.01s  0.14% 93.39%      0.29s  4.08%  reflect.typedmemmove
     0.01s  0.14% 93.53%      0.04s  0.56%  reflect.unpackEface (inline)
     0.01s  0.14% 93.67%      0.28s  3.94%  runtime.suspendG
     0.01s  0.14% 93.81%      0.14s  1.97%  strconv.ryuFtoaShortest
```

Roughly 6.4 seconds.

## Sorting object keys

Now one thing we notice is that it spends a good chunk of time in sort
functions. In fact, it is hardcoded in Go's JSON implementation to
require sorting of object keys. The most common data in DataStation is
arrays of objects representing rows of data. This JSON is an
intermediate representation so there's no value in DataStation/dsq to
having keys sorted.

Could we improve performance if we wrote a specialization of the
builtin JSON library that skips sorting JSON object keys if the
overall object to be written is an array of objects? We'll only care
about the top-level object keys. If there are nested objects we won't
bother about that. Within nested objects we'll just use the existing
Go JSON encoder. Having a fallback and internally using the Go JSON
encoder makes this a pretty safe and simple approach.

Let's try a basic implementation.

```go
$ cp main.go nosort.go
$ diff -u main.go nosort.go
--- main.go     2022-03-03 14:25:01.530812750 +0000
+++ nosort.go   2022-03-03 14:25:01.530812750 +0000
@@ -2,11 +2,85 @@

 import (
        "encoding/json"
+       "log"
        "os"
+       "strconv"

        "github.com/pkg/profile"
 )

+func nosortEncoder(out *os.File, obj interface{}) error {
+       a, ok := obj.([]interface{})
+       // Fall back to normal encoder
+       if !ok {
+               log.Println("Falling back to stdlib")
+               return stdlibEncoder(out, obj)
+       }
+
+       _, err := out.Write([]byte("["))
+       if err != nil {
+               return err
+       }
+
+       encoder := json.NewEncoder(out)
+
+       for i, row := range a {
+               // Write a comma before the current object
+               if i > 0 {
+                       _, err = out.Write([]byte(",\n"))
+                       if err != nil {
+                               return err
+                       }
+               }
+
+               r, ok := row.(map[string]interface{})
+               if !ok {
+                       log.Println("Falling back to stdlib")
+                       err = encoder.Encode(r)
+                       if err != nil {
+                               return err
+                       }
+                       continue
+               }
+
+               _, err := out.Write([]byte("{"))
+               if err != nil {
+                       return err
+               }
+
+               j := -1
+               for col, val := range r {
+                       j += 1
+
+                       // Write a comma before the current key-value
+                       if j > 0 {
+                               _, err = out.Write([]byte(","))
+                               if err != nil {
+                                       return err
+                               }
+                       }
+
+                       _, err = out.Write([]byte(strconv.QuoteToASCII(col) + ":"))
+                       if err != nil {
+                               return err
+                       }
+
+                       err = encoder.Encode(val)
+                       if err != nil {
+                               return err
+                       }
+               }
+
+               _, err = out.Write([]byte("}"))
+               if err != nil {
+                       return err
+               }
+       }
+
+       _, err = out.Write([]byte("]"))
+       return err
+}
+
 func stdlibEncoder(out *os.File, obj interface{}) error {
        encoder := json.NewEncoder(out)
        return encoder.Encode(obj)
@@ -29,6 +103,8 @@
                        switch encoderArg {
                        case "stdlib":
                                encoder = stdlibEncoder
+                       case "nosort":
+                               encoder = nosortEncoder
                        default:
                                panic("Unknown encoder: " + encoderArg)
                        }
```

Very simple code that just does some type checking and mostly spends
time writing JSON wrapper syntax, with calls to Go’s builtin JSON
library inside of objects. The only funky thing in there you may
notice is the `strconv.QuoteToAscii` call. This merely quotes and
escapes nested quotes. This is necessary since escaped nested quotes
are valid within a JSON object key.

Let's build and run, passing the new encoder name to `main`.

```bash
$ go build -o main nosort.go
$ ./main --in wide --encoder nosort
2022/03/03 15:53:51 profile: cpu profiling enabled, /tmp/profile1940788787/cpu.pprof
2022/03/03 15:54:40 profile: cpu profiling disabled, /tmp/profile1940788787/cpu.pprof
```

Roughly 49 seconds. Woah. That’s way slower than the builtin JSON
library. But let’s dig in with pprof to understand why. Since we
should be doing exactly what the Go library does but not sorting, it
shouldn’t be possible that we’re slower.

```bash
$ go tool pprof -top /tmp/profile1940788787/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 3:53pm (UTC)
Duration: 48.86s, Total samples = 47.64s (97.51%)
Showing nodes accounting for 45.44s, 95.38% of 47.64s total
Dropped 87 nodes (cum <= 0.24s)
      flat  flat%   sum%        cum   cum%
    39.58s 83.08% 83.08%     41.57s 87.26%  syscall.Syscall
     1.60s  3.36% 86.44%      1.72s  3.61%  encoding/json.(*encodeState).string
     0.62s  1.30% 87.74%      0.71s  1.49%  runtime.casgstatus
     0.51s  1.07% 88.81%      0.97s  2.04%  strconv.appendQuotedWith
     0.40s  0.84% 89.65%      0.93s  1.95%  runtime.reentersyscall
     0.34s  0.71% 90.37%      0.46s  0.97%  strconv.appendEscapedRune
     0.29s  0.61% 90.97%      0.48s  1.01%  runtime.exitsyscallfast
     0.27s  0.57% 91.54%      1.04s  2.18%  runtime.exitsyscall
     0.26s  0.55% 92.09%      0.26s  0.55%  runtime.memmove
     0.23s  0.48% 92.57%      0.42s  0.88%  runtime.mallocgc
     0.22s  0.46% 93.03%      0.31s  0.65%  runtime.mapaccess2
     0.21s  0.44% 93.47%     42.35s 88.90%  internal/poll.(*FD).Write
     0.14s  0.29% 93.77%      0.28s  0.59%  runtime.concatstrings
     0.13s  0.27% 94.04%     47.63s   100%  main.nosortEncoder
     0.08s  0.17% 94.21%      0.49s  1.03%  sync.(*Map).Load
     0.07s  0.15% 94.35%     17.57s 36.88%  encoding/json.(*Encoder).Encode
     0.07s  0.15% 94.50%     42.42s 89.04%  os.(*File).write (inline)
     0.06s  0.13% 94.63%     42.49s 89.19%  os.(*File).Write
     0.05s   0.1% 94.73%      0.26s  0.55%  internal/poll.(*FD).writeUnlock
     0.05s   0.1% 94.84%      0.24s   0.5%  strconv.genericFtoa
     0.05s   0.1% 94.94%     41.62s 87.36%  syscall.write
     0.04s 0.084% 95.03%      2.65s  5.56%  encoding/json.(*encodeState).reflectValue
     0.03s 0.063% 95.09%      2.72s  5.71%  encoding/json.(*encodeState).marshal
     0.03s 0.063% 95.15%      0.31s  0.65%  runtime.concatstring2
     0.02s 0.042% 95.19%      0.30s  0.63%  encoding/json.floatEncoder.encode
     0.02s 0.042% 95.24%     41.64s 87.41%  internal/poll.ignoringEINTRIO (inline)
     0.02s 0.042% 95.28%      0.95s  1.99%  runtime.entersyscall
     0.02s 0.042% 95.32%      0.44s  0.92%  runtime.makeslice
     0.01s 0.021% 95.34%      1.81s  3.80%  encoding/json.stringEncoder
     0.01s 0.021% 95.36%      0.50s  1.05%  encoding/json.typeEncoder
     0.01s 0.021% 95.38%      1.48s  3.11%  strconv.quoteWith (inline)
         0     0% 95.38%      0.50s  1.05%  encoding/json.valueEncoder
         0     0% 95.38%     47.63s   100%  main.main
         0     0% 95.38%     47.63s   100%  runtime.main
         0     0% 95.38%      0.24s   0.5%  strconv.AppendFloat (inline)
         0     0% 95.38%      1.48s  3.11%  strconv.QuoteToASCII (inline)
         0     0% 95.38%     41.62s 87.36%  syscall.Write (inline)
```

## Buffered I/O

Ok so in this case we spend a huge amount of time in the write
syscall. The traditional way to get around this is to used buffered IO
so you’re not actually calling the write syscall all the time. Let’s
give that a shot.

```bash
$ cp nosort.go bufio.go
$ diff -u nosort.go bufio.go
--- nosort.go   2022-03-03 14:25:01.530812750 +0000
+++ bufio.go    2022-03-03 15:56:51.741269676 +0000
@@ -1,6 +1,7 @@
 package main

 import (
+       "bufio"
        "encoding/json"
        "log"
        "os"
@@ -17,17 +18,20 @@
                return stdlibEncoder(out, obj)
        }

-       _, err := out.Write([]byte("["))
+       bo := bufio.NewWriter(out)
+       defer bo.Flush()
+       _, err := bo.Write([]byte("["))
        if err != nil {
                return err
        }

-       encoder := json.NewEncoder(out)
+       // For fallback and internals
+       encoder := json.NewEncoder(bo)

        for i, row := range a {
                // Write a comma before the current object
                if i > 0 {
-                       _, err = out.Write([]byte(",\n"))
+                       _, err = bo.Write([]byte(",\n"))
                        if err != nil {
                                return err
                        }
@@ -43,7 +47,7 @@
                        continue
                }

-               _, err := out.Write([]byte("{"))
+               _, err := bo.Write([]byte("{"))
                if err != nil {
                        return err
                }
@@ -54,13 +58,13 @@

                        // Write a comma before the current key-value
                        if j > 0 {
-                               _, err = out.Write([]byte(","))
+                               _, err = bo.Write([]byte(","))
                                if err != nil {
                                        return err
                                }
                        }

-                       _, err = out.Write([]byte(strconv.QuoteToASCII(col) + ":"))
+                       _, err = bo.Write([]byte(strconv.QuoteToASCII(col) + ":"))
                        if err != nil {
                                return err
                        }
@@ -71,13 +75,13 @@
                        }
                }

-               _, err = out.Write([]byte("}"))
+               _, err = bo.Write([]byte("}"))
                if err != nil {
                        return err
                }
        }

-       _, err = out.Write([]byte("]"))
+       _, err = bo.Write([]byte("]"))
        return err
 }
```

Build it and run it:

```bash
$ go build -o main bufio.go
$ ./main --in wide --encoder nosort
2022/03/03 15:57:45 profile: cpu profiling enabled, /tmp/profile2431608829/cpu.pprof
2022/03/03 15:57:50 profile: cpu profiling disabled, /tmp/profile2431608829/cpu.pprof
```

And hey! 5 seconds. We're already beating the standard library. But
let’s see where we’re spending time now.

```bash
$ go tool pprof -top  /tmp/profile2431608829/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 3:57pm (UTC)
Duration: 5.71s, Total samples = 5.56s (97.33%)
Showing nodes accounting for 5.26s, 94.60% of 5.56s total
Dropped 35 nodes (cum <= 0.03s)
      flat  flat%   sum%        cum   cum%
     1.47s 26.44% 26.44%      1.56s 28.06%  encoding/json.(*encodeState).string
     0.72s 12.95% 39.39%      0.75s 13.49%  syscall.Syscall
     0.42s  7.55% 46.94%      0.79s 14.21%  strconv.appendQuotedWith
     0.26s  4.68% 51.62%      0.36s  6.47%  strconv.appendEscapedRune
     0.25s  4.50% 56.12%      0.49s  8.81%  runtime.mallocgc
     0.21s  3.78% 59.89%      0.21s  3.78%  runtime.memmove
     0.18s  3.24% 63.13%      0.25s  4.50%  runtime.concatstrings
     0.16s  2.88% 66.01%      0.99s 17.81%  bufio.(*Writer).Write
     0.11s  1.98% 67.99%      0.17s  3.06%  runtime.mapiternext
     0.11s  1.98% 69.96%      0.11s  1.98%  runtime.nextFreeFast (inline)
     0.10s  1.80% 71.76%      0.10s  1.80%  strconv.IsPrint
     0.09s  1.62% 73.38%      0.11s  1.98%  sync.(*Pool).Put
     0.08s  1.44% 74.82%      0.17s  3.06%  runtime.mapaccess2
     0.07s  1.26% 76.08%      0.07s  1.26%  reflect.Value.String
     0.07s  1.26% 77.34%      0.32s  5.76%  runtime.concatstring2
     0.07s  1.26% 78.60%      0.07s  1.26%  runtime.memclrNoHeapPointers
     0.06s  1.08% 79.68%      0.27s  4.86%  sync.(*Map).Load
     0.05s   0.9% 80.58%      3.35s 60.25%  encoding/json.(*Encoder).Encode
     0.05s   0.9% 81.47%      0.09s  1.62%  strconv.ryuDigits
     0.04s  0.72% 82.19%      0.04s  0.72%  bytes.(*Buffer).WriteByte
     0.04s  0.72% 82.91%      1.69s 30.40%  encoding/json.stringEncoder
     0.04s  0.72% 83.63%      0.04s  0.72%  reflect.Value.Type
     0.04s  0.72% 84.35%      0.04s  0.72%  runtime.(*bmap).overflow (inline)
     0.04s  0.72% 85.07%      0.04s  0.72%  runtime.add (partial-inline)
     0.04s  0.72% 85.79%      0.35s  6.29%  runtime.stringtoslicebyte
     0.04s  0.72% 86.51%      1.05s 18.88%  strconv.quoteWith (inline)
     0.04s  0.72% 87.23%      0.04s  0.72%  strconv.ryuDigits32
     0.04s  0.72% 87.95%      0.07s  1.26%  sync.(*Pool).pin
     0.04s  0.72% 88.67%      0.04s  0.72%  sync.(*entry).load (inline)
     0.03s  0.54% 89.21%      2.26s 40.65%  encoding/json.(*encodeState).marshal
     0.03s  0.54% 89.75%      0.19s  3.42%  runtime.makeslice
     0.03s  0.54% 90.29%      0.06s  1.08%  runtime.nilinterhash
     0.03s  0.54% 90.83%      0.03s  0.54%  runtime.slicebytetostring
     0.03s  0.54% 91.37%      0.13s  2.34%  strconv.genericFtoa
     0.02s  0.36% 91.73%      0.18s  3.24%  encoding/json.floatEncoder.encode
     0.02s  0.36% 92.09%      5.56s   100%  main.nosortEncoder
     0.02s  0.36% 92.45%      0.05s   0.9%  reflect.ValueOf (inline)
     0.02s  0.36% 92.81%      0.28s  5.04%  runtime.rawbyteslice
     0.02s  0.36% 93.17%      0.07s  1.26%  sync.(*Pool).Get
     0.01s  0.18% 93.35%      0.77s 13.85%  bufio.(*Writer).Flush
     0.01s  0.18% 93.53%      0.09s  1.62%  encoding/json.newEncodeState
     0.01s  0.18% 93.71%      0.28s  5.04%  encoding/json.typeEncoder
     0.01s  0.18% 93.88%      0.31s  5.58%  encoding/json.valueEncoder
     0.01s  0.18% 94.06%      0.12s  2.16%  runtime.newobject
     0.01s  0.18% 94.24%      0.03s  0.54%  runtime.typehash
     0.01s  0.18% 94.42%      0.14s  2.52%  strconv.AppendFloat (inline)
     0.01s  0.18% 94.60%      0.03s  0.54%  sync.runtime_procPin
         0     0% 94.60%      0.08s  1.44%  bytes.(*Buffer).WriteString
         0     0% 94.60%      2.18s 39.21%  encoding/json.(*encodeState).reflectValue
         0     0% 94.60%      0.76s 13.67%  internal/poll.(*FD).Write
         0     0% 94.60%      0.75s 13.49%  internal/poll.ignoringEINTRIO (inline)
         0     0% 94.60%      5.56s   100%  main.main
         0     0% 94.60%      0.76s 13.67%  os.(*File).Write
         0     0% 94.60%      0.76s 13.67%  os.(*File).write (inline)
         0     0% 94.60%      0.07s  1.26%  runtime.(*mcache).nextFree
         0     0% 94.60%      0.06s  1.08%  runtime.(*mcache).refill
         0     0% 94.60%      0.05s   0.9%  runtime.(*mcentral).cacheSpan
         0     0% 94.60%      0.04s  0.72%  runtime.(*mcentral).grow
         0     0% 94.60%      0.03s  0.54%  runtime.(*mheap).alloc
         0     0% 94.60%      5.56s   100%  runtime.main
         0     0% 94.60%      1.05s 18.88%  strconv.QuoteToASCII (inline)
         0     0% 94.60%      0.09s  1.62%  strconv.ryuFtoaShortest
         0     0% 94.60%      0.75s 13.49%  syscall.Write (inline)
         0     0% 94.60%      0.75s 13.49%  syscall.write
```

## Infinite buffer

Surprisingly, we’re still spending a big chunk of time in a write
syscall. If we look at the [source code for
bufio](https://cs.opensource.google/go/go/+/refs/tags/go1.17.7:src/bufio/bufio.go;drc=refs%2Ftags%2Fgo1.17.7;l=19),
we can see that the default size if 4096. So in a big file like this
we’ll still be calling the write syscall a lot.

Now bufio.Writer has an odd interface. We can only specify an exact
size for the internal buffer. We could raise this to be the max size
of integers but then that would be a huge chunk of memory we always
allocate. That doesn’t really make sense.

We could instead use a bytes.Buffer that is allowed to grow. Then we
only write to the file once it’s full. A lazier approach would be to
ignore it getting full (which will just cause an error to be returned
eventually and the whole encoder to fail) and just copy from the
buffer to the file once at the end. Let’s give that a shot.

```bash
$ cp bufio.go buffer.go
$ diff -u bufio.go buffer.go
--- bufio.go    2022-03-03 15:56:51.741269676 +0000
+++ buffer.go   2022-03-03 14:25:01.528812772 +0000
@@ -1,7 +1,7 @@
 package main

 import (
-       "bufio"
+       "bytes"
        "encoding/json"
        "log"
        "os"
@@ -18,8 +18,7 @@
                return stdlibEncoder(out, obj)
        }

-       bo := bufio.NewWriter(out)
-       defer bo.Flush()
+       bo := bytes.NewBuffer(nil)
        _, err := bo.Write([]byte("["))
        if err != nil {
                return err
@@ -82,6 +81,14 @@
        }

        _, err = bo.Write([]byte("]"))
+
+       for bo.Len() > 0 {
+               _, err := bo.WriteTo(out)
+               if err != nil {
+                       return err
+               }
+       }
+
        return err
 }
```

And run it.

```bash
$ go build -o main buffer.go
$ benchmarks2 ./main --in wide --encoder nosort
2022/03/03 16:02:33 profile: cpu profiling enabled, /tmp/profile3851693206/cpu.pprof
2022/03/03 16:02:38 profile: cpu profiling disabled, /tmp/profile3851693206/cpu.pprof
$ go tool pprof -top  /tmp/profile3851693206/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 4:02pm (UTC)
Duration: 5.22s, Total samples = 6.09s (116.69%)
Showing nodes accounting for 5.66s, 92.94% of 6.09s total
Dropped 67 nodes (cum <= 0.03s)
      flat  flat%   sum%        cum   cum%
     1.25s 20.53% 20.53%      1.44s 23.65%  encoding/json.(*encodeState).string
     0.60s  9.85% 30.38%      0.60s  9.85%  runtime.memmove
     0.51s  8.37% 38.75%      0.80s 13.14%  strconv.appendQuotedWith
     0.39s  6.40% 45.16%      1.14s 18.72%  runtime.scanobject
     0.31s  5.09% 50.25%      0.31s  5.09%  runtime.procyield
     0.23s  3.78% 54.02%      0.23s  3.78%  runtime.pageIndexOf (inline)
     0.19s  3.12% 57.14%      0.29s  4.76%  strconv.appendEscapedRune
     0.15s  2.46% 59.61%      0.22s  3.61%  runtime.findObject
     0.14s  2.30% 61.90%      0.36s  5.91%  runtime.mallocgc
     0.12s  1.97% 63.88%      0.61s 10.02%  bytes.(*Buffer).Write
     0.12s  1.97% 65.85%      0.13s  2.13%  runtime.mapiternext
     0.11s  1.81% 67.65%      0.17s  2.79%  runtime.concatstrings
     0.10s  1.64% 69.29%      0.40s  6.57%  runtime.greyobject
     0.10s  1.64% 70.94%      0.10s  1.64%  runtime.memclrNoHeapPointers
     0.10s  1.64% 72.58%      0.10s  1.64%  strconv.IsPrint
     0.08s  1.31% 73.89%      0.25s  4.11%  sync.(*Map).Load
     0.07s  1.15% 75.04%      0.07s  1.15%  reflect.Value.String
     0.07s  1.15% 76.19%      0.07s  1.15%  runtime.heapBits.bits (inline)
     0.07s  1.15% 77.34%      0.07s  1.15%  strconv.ryuDigits32
     0.06s  0.99% 78.33%      0.09s  1.48%  bytes.(*Buffer).WriteByte
     0.06s  0.99% 79.31%      0.06s  0.99%  runtime.heapBits.next (inline)
     0.05s  0.82% 80.13%      0.05s  0.82%  encoding/json.(*encodeState).marshal.func1
     0.05s  0.82% 80.95%      0.22s  3.61%  runtime.concatstring2
     0.05s  0.82% 81.77%      0.41s  6.73%  runtime.makeslice
     0.05s  0.82% 82.59%      0.05s  0.82%  runtime.nextFreeFast (inline)
     0.05s  0.82% 83.42%      0.05s  0.82%  runtime.spanOf (inline)
     0.05s  0.82% 84.24%      0.05s  0.82%  sync.(*entry).load (inline)
     0.04s  0.66% 84.89%      0.14s  2.30%  bytes.(*Buffer).WriteString
     0.04s  0.66% 85.55%      0.04s  0.66%  bytes.(*Buffer).tryGrowByReslice
     0.04s  0.66% 86.21%      2.79s 45.81%  encoding/json.(*Encoder).Encode
     0.04s  0.66% 86.86%      4.58s 75.21%  main.nosortEncoder
     0.04s  0.66% 87.52%      0.12s  1.97%  runtime.mapaccess2
     0.04s  0.66% 88.18%      0.04s  0.66%  runtime.procUnpin (inline)
     0.04s  0.66% 88.83%      0.08s  1.31%  runtime.slicebytetostring
     0.03s  0.49% 89.33%      2.13s 34.98%  encoding/json.(*encodeState).marshal
     0.03s  0.49% 89.82%      1.50s 24.63%  runtime.gcDrain
     0.03s  0.49% 90.31%      0.06s  0.99%  strconv.formatDigits
     0.03s  0.49% 90.80%      0.19s  3.12%  strconv.genericFtoa
     0.02s  0.33% 91.13%      0.23s  3.78%  encoding/json.floatEncoder.encode
     0.02s  0.33% 91.46%      1.54s 25.29%  encoding/json.stringEncoder
     0.02s  0.33% 91.79%      0.04s  0.66%  sync.(*Pool).Put
     0.01s  0.16% 91.95%      2.04s 33.50%  encoding/json.(*encodeState).reflectValue
     0.01s  0.16% 92.12%      0.09s  1.48%  encoding/json.newEncodeState
     0.01s  0.16% 92.28%      0.26s  4.27%  encoding/json.valueEncoder
     0.01s  0.16% 92.45%      0.05s  0.82%  runtime.(*mcache).nextFree
     0.01s  0.16% 92.61%      1.20s 19.70%  strconv.QuoteToASCII (inline)
     0.01s  0.16% 92.78%      0.10s  1.64%  strconv.ryuDigits
     0.01s  0.16% 92.94%      0.06s  0.99%  sync.(*Pool).Get
         0     0% 92.94%      0.34s  5.58%  bytes.(*Buffer).grow
         0     0% 92.94%      0.10s  1.64%  bytes.makeSlice
         0     0% 92.94%      0.25s  4.11%  encoding/json.typeEncoder
         0     0% 92.94%      4.58s 75.21%  main.main
         0     0% 92.94%      0.06s  0.99%  runtime.(*mcache).allocLarge
         0     0% 92.94%      1.50s 24.63%  runtime.gcBgMarkWorker
         0     0% 92.94%      1.50s 24.63%  runtime.gcBgMarkWorker.func2
         0     0% 92.94%      0.06s  0.99%  runtime.heapBits.initSpan
         0     0% 92.94%      4.58s 75.21%  runtime.main
         0     0% 92.94%      0.34s  5.58%  runtime.markroot
         0     0% 92.94%      0.34s  5.58%  runtime.markroot.func1
         0     0% 92.94%      0.04s  0.66%  runtime.memclrNoHeapPointersChunked
         0     0% 92.94%      0.34s  5.58%  runtime.suspendG
         0     0% 92.94%      1.53s 25.12%  runtime.systemstack
         0     0% 92.94%      0.19s  3.12%  strconv.AppendFloat (inline)
         0     0% 92.94%      1.19s 19.54%  strconv.quoteWith (inline)
         0     0% 92.94%      0.10s  1.64%  strconv.ryuFtoaShortest
         0     0% 92.94%      0.04s  0.66%  sync.runtime_procUnpin
```

Down another half second-ish. Nice! And hey! Syscall is no longer in
there.

## Column caching

Now we’re getting to the end of useful changes we can make but I
notice `strconv.appendQuotedWith` and `strconv.appendEscapedRune`. We
may be able to shave off a little bit by caching the columns rather
than escaping all columns again each time for every row. Let’s try it.

```bash
$ cp buffer.go cache-columns.go
$ diff -u buffer.go cache-columns.go
--- buffer.go   2022-03-03 14:25:01.528812772 +0000
+++ cache-columns.go    2022-03-03 14:48:50.003217039 +0000
@@ -27,6 +27,8 @@
        // For fallback and internals
        encoder := json.NewEncoder(bo)

+       quotedColumns := map[string][]byte{}
+
        for i, row := range a {
                // Write a comma before the current object
                if i > 0 {
@@ -63,7 +65,12 @@
                                }
                        }

-                       _, err = bo.Write([]byte(strconv.QuoteToASCII(col) + ":"))
+                       quoted := quotedColumns[col]
+                       if quoted == nil {
+                               quoted = []byte(strconv.QuoteToASCII(col) + ":")
+                               quotedColumns[col] = quoted
+                       }
+                       _, err = bo.Write(quoted)
                        if err != nil {
                                return err
                        }
```

And run it.

```
$ go build -o main.go cache-columns.go
$ ./main --in wide --encoder nosort
2022/03/03 16:27:33 profile: cpu profiling enabled, /tmp/profile1596098633/cpu.pprof
2022/03/03 16:27:38 profile: cpu profiling disabled, /tmp/profile1596098633/cpu.pprof
$ go tool pprof -top /tmp/profile1596098633/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 4:27pm (UTC)
Duration: 4.40s, Total samples = 5.21s (118.46%)
Showing nodes accounting for 4.85s, 93.09% of 5.21s total
Dropped 46 nodes (cum <= 0.03s)
      flat  flat%   sum%        cum   cum%
     1.39s 26.68% 26.68%      1.54s 29.56%  encoding/json.(*encodeState).string
     0.50s  9.60% 36.28%      0.50s  9.60%  runtime.memmove
     0.49s  9.40% 45.68%      1.02s 19.58%  runtime.scanobject
     0.32s  6.14% 51.82%      0.32s  6.14%  runtime.procyield
     0.15s  2.88% 54.70%      0.15s  2.88%  aeshashbody
     0.12s  2.30% 57.01%      0.16s  3.07%  runtime.findObject
     0.11s  2.11% 59.12%      0.38s  7.29%  runtime.mapaccess1_faststr
     0.11s  2.11% 61.23%      0.11s  2.11%  runtime.memclrNoHeapPointers
     0.11s  2.11% 63.34%      0.11s  2.11%  runtime.pageIndexOf (inline)
     0.10s  1.92% 65.26%      0.10s  1.92%  memeqbody
     0.09s  1.73% 66.99%      0.66s 12.67%  bytes.(*Buffer).Write
     0.09s  1.73% 68.71%      0.09s  1.73%  bytes.(*Buffer).tryGrowByReslice (inline)
     0.09s  1.73% 70.44%      3.79s 72.74%  main.nosortEncoder
     0.08s  1.54% 71.98%      2.20s 42.23%  encoding/json.(*encodeState).reflectValue
     0.08s  1.54% 73.51%      0.16s  3.07%  runtime.mapaccess2
     0.08s  1.54% 75.05%      0.17s  3.26%  strconv.genericFtoa
     0.07s  1.34% 76.39%      2.30s 44.15%  encoding/json.(*encodeState).marshal
     0.07s  1.34% 77.74%      0.24s  4.61%  runtime.greyobject
     0.07s  1.34% 79.08%      0.16s  3.07%  runtime.mapiternext
     0.06s  1.15% 80.23%      0.06s  1.15%  runtime.add (inline)
     0.05s  0.96% 81.19%      0.05s  0.96%  reflect.Value.String
     0.05s  0.96% 82.15%      0.05s  0.96%  runtime.heapBits.bits (inline)
     0.05s  0.96% 83.11%      0.05s  0.96%  strconv.ryuDigits32
     0.04s  0.77% 83.88%      0.09s  1.73%  sync.(*Pool).Put
     0.03s  0.58% 84.45%      0.14s  2.69%  bytes.(*Buffer).WriteString
     0.03s  0.58% 85.03%      2.97s 57.01%  encoding/json.(*Encoder).Encode
     0.03s  0.58% 85.60%      0.03s  0.58%  encoding/json.(*encodeState).marshal.func1
     0.03s  0.58% 86.18%      1.39s 26.68%  runtime.gcDrain
     0.03s  0.58% 86.76%      0.04s  0.77%  runtime.heapBits.next (inline)
     0.03s  0.58% 87.33%      0.03s  0.58%  runtime.heapBitsForAddr
     0.03s  0.58% 87.91%      0.20s  3.84%  sync.(*Map).Load
     0.03s  0.58% 88.48%      0.07s  1.34%  sync.(*Pool).Get
     0.03s  0.58% 89.06%      0.07s  1.34%  sync.(*Pool).pin
     0.02s  0.38% 89.44%      0.04s  0.77%  bytes.(*Buffer).WriteByte
     0.02s  0.38% 89.83%      0.26s  4.99%  encoding/json.floatEncoder.encode
     0.02s  0.38% 90.21%      0.09s  1.73%  encoding/json.newEncodeState
     0.02s  0.38% 90.60%      0.22s  4.22%  encoding/json.typeEncoder
     0.02s  0.38% 90.98%      0.26s  4.99%  encoding/json.valueEncoder
     0.02s  0.38% 91.36%      0.05s  0.96%  runtime.nilinterhash
     0.02s  0.38% 91.75%      0.03s  0.58%  runtime.typehash
     0.02s  0.38% 92.13%      0.07s  1.34%  strconv.ryuDigits
     0.02s  0.38% 92.51%      0.03s  0.58%  sync.runtime_procPin
     0.01s  0.19% 92.71%      1.60s 30.71%  encoding/json.stringEncoder
     0.01s  0.19% 92.90%      0.03s  0.58%  runtime.(*bmap).overflow (inline)
     0.01s  0.19% 93.09%      0.03s  0.58%  runtime.nilinterequal
         0     0% 93.09%      0.26s  4.99%  bytes.(*Buffer).grow
         0     0% 93.09%      0.11s  2.11%  bytes.makeSlice
         0     0% 93.09%      3.79s 72.74%  main.main
         0     0% 93.09%      0.05s  0.96%  runtime.(*mcache).allocLarge
         0     0% 93.09%      1.39s 26.68%  runtime.gcBgMarkWorker
         0     0% 93.09%      1.39s 26.68%  runtime.gcBgMarkWorker.func2
         0     0% 93.09%      0.05s  0.96%  runtime.heapBits.initSpan
         0     0% 93.09%      3.79s 72.74%  runtime.main
         0     0% 93.09%      0.11s  2.11%  runtime.makeslice
         0     0% 93.09%      0.11s  2.11%  runtime.mallocgc
         0     0% 93.09%      0.34s  6.53%  runtime.markroot
         0     0% 93.09%      0.34s  6.53%  runtime.markroot.func1
         0     0% 93.09%      0.03s  0.58%  runtime.mcall
         0     0% 93.09%      0.06s  1.15%  runtime.memclrNoHeapPointersChunked
         0     0% 93.09%      0.34s  6.53%  runtime.suspendG
         0     0% 93.09%      1.40s 26.87%  runtime.systemstack
         0     0% 93.09%      0.17s  3.26%  strconv.AppendFloat (inline)
         0     0% 93.09%      0.07s  1.34%  strconv.ryuFtoaShortest
```

Not bad! This is about as far as I can figure out how to take this without making massive new changes. So let's call it a day on this nosort implementation.

## goccy/go-json

Now I wonder how this implementation compares to other existing
libraries that improve on the Go standard libraries JSON encoder.

Let's add [goccy/go-json](https://github.com/goccy/go-json) which
bills itself as the fastest encoder. Let's drop `pkg/profile` and
really soling on timings taken before and after the `encode` function
is called. And let's beef up the benchmark script a bit more to be
able to run multiple iterations and multiple kinds of encoders.

```
$ cp cache-columns.go goccy.go
$ diff -u cache-columns.go goccy.go
--- cache-columns.go    2022-03-03 14:48:50.003217039 +0000
+++ goccy.go    2022-03-03 15:48:08.899932125 +0000
@@ -3,11 +3,15 @@
 import (
        "bytes"
        "encoding/json"
+       "fmt"
        "log"
        "os"
+       "runtime"
        "strconv"
+       "strings"
+       "time"

-       "github.com/pkg/profile"
+       goccy_json "github.com/goccy/go-json"
 )

 func nosortEncoder(out *os.File, obj interface{}) error {
@@ -24,7 +28,6 @@
                return err
        }

-       // For fallback and internals
        encoder := json.NewEncoder(bo)

        quotedColumns := map[string][]byte{}
@@ -104,10 +107,16 @@
        return encoder.Encode(obj)
 }

+func goccy_jsonEncoder(out *os.File, obj interface{}) error {
+       encoder := goccy_json.NewEncoder(out)
+       return encoder.Encode(obj)
+}
+
 func main() {
        var in string
-       encoderArg := "stdlib"
-       encoder := stdlibEncoder
+       nTimes := 1
+       encoders := []func(*os.File, interface{}) error{stdlibEncoder}
+       encoderArgs := []string{"stdlib"}

        for i, arg := range os.Args {
                if arg == "--in" {
@@ -116,15 +125,29 @@
                        continue
                }

-               if arg == "--encoder" {
-                       encoderArg = os.Args[i+1]
-                       switch encoderArg {
-                       case "stdlib":
-                               encoder = stdlibEncoder
-                       case "nosort":
-                               encoder = nosortEncoder
-                       default:
-                               panic("Unknown encoder: " + encoderArg)
+               if arg == "--ntimes" {
+                       var err error
+                       nTimes, err = strconv.Atoi(os.Args[i+1])
+                       if err != nil {
+                               panic(err)
+                       }
+
+                       i += 1
+                       continue
+               }
+
+               if arg == "--encoders" {
+                       encoderArgs = strings.Split(os.Args[i+1], ",")
+                       encoders = nil
+                       for _, a := range encoderArgs {
+                               switch a {
+                               case "stdlib":
+                                       encoders = append(encoders, stdlibEncoder)
+                               case "nosort":
+                                       encoders = append(encoders, nosortEncoder)
+                               case "goccy_json":
+                                       encoders = append(encoders, goccy_jsonEncoder)
+                               }
                        }
                        i += 1
                        continue
@@ -144,16 +167,25 @@
                panic(err)
        }

-       fw, err := os.OpenFile(in+"-"+encoderArg+".json", os.O_TRUNC|os.O_WRONLY|os.O_CREATE, os.ModePerm)
-       if err != nil {
-               panic(err)
-       }
-       defer fw.Close()
+       fmt.Println("sample,encoder,time")
+       for i, encoder := range encoders {
+               encoderArg := encoderArgs[i]
+               fw, err := os.OpenFile(in+"-"+encoderArg+".json", os.O_TRUNC|os.O_WRONLY|os.O_CREATE, os.ModePerm)
+               if err != nil {
+                       panic(err)
+               }
+               defer fw.Close()

-       p := profile.Start()
-       defer p.Stop()
-       err = encoder(fw, o)
-       if err != nil {
-               panic(err)
+               for i := 0; i < nTimes; i++ {
+                       t1 := time.Now()
+                       err = encoder(fw, o)
+                       t2 := time.Now()
+                       if err != nil {
+                               panic(err)
+                       }
+
+                       fmt.Printf("%s,%s,%s\n", in, encoderArg, t2.Sub(t1))
+                       runtime.GC()
+               }
        }
 }
```

One important thing to call out here is `runtime.GC()` which forces
the GC to run in-between tests rather than during them. This helps
make the GC more predictable and less likely to influence timings
during encoding. Without this you'd see a massive growth in time taken
ever 3/4 runs.

Let's try it out.

```
$ go build -o main goccy.go
$ ./main --in wide --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
wide,nosort,4.154467624s
wide,nosort,4.593214155s
wide,nosort,4.486129927s
wide,nosort,4.536035464s
wide,nosort,4.566813196s
wide,goccy_json,5.269642489s
wide,goccy_json,5.148214964s
wide,goccy_json,5.5261154s
wide,goccy_json,4.792188969s
wide,goccy_json,3.768667068s
wide,stdlib,6.716863082s
wide,stdlib,6.884371048s
wide,stdlib,6.058346158s
wide,stdlib,6.709027109s
wide,stdlib,6.82861509s
```

Woah! This was a genuine surprise. Most other benchmarks I did showed
goccy/go-json as being faster than this nosort implementation. So
let's try some other datasets.

```bash
$ ./main --in long --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
long,nosort,5.212509176s
long,nosort,7.304829374s
long,nosort,5.313968299s
long,nosort,5.378680587s
long,nosort,5.408050889s
long,goccy_json,6.283394284s
long,goccy_json,6.091520274s
long,goccy_json,5.513058491s
long,goccy_json,4.494986358s
long,goccy_json,4.680172512s
long,stdlib,8.829198183s
long,stdlib,8.534747336s
long,stdlib,7.944806863s
long,stdlib,8.953913363s
long,stdlib,8.3021362s
```

So what we can see already is that this nosort implementation seems to
perform pretty well with large datasets, shaving 2-3 seconds off of
the standard library implementation.

#### Share
{% endblock %}
