{% extends "blog/layout.tmpl" %}

{% block postTitle %}Speeding up Go's builtin JSON encoder up to 55% for large arrays of objects{% endblock %}
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

All code for these benchmarks are [available on
Github](https://github.com/multiprocessio/go-json-benchmarks).

The resulting JSON encoder library is also [available on Github](https://github.com/multiprocessio/go-json).

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
+++ nosort.go   2022-03-03 18:58:35.227829357 +0000
@@ -2,11 +2,94 @@

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
+                       bs, err := json.Marshal(row)
+                       if err != nil {
+                               return err
+                       }
+
+                       _, err = out.Write(bs)
+                       if err != nil {
+                               return err
+                       }
+
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
+                       bs, err := json.Marshal(val)
+                       if err != nil {
+                               return err
+                       }
+
+                       _, err = out.Write(bs)
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
@@ -29,6 +112,8 @@
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
time writing JSON wrapper syntax, with calls to Go's builtin JSON
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

Roughly 49 seconds. Woah. That's way slower than the builtin JSON
library. But let's dig in with pprof to understand why. Since we
should be doing exactly what the Go library does but not sorting, it
shouldn't be possible that we're slower.

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
so you're not actually calling the write syscall all the time. Let's
give that a shot.

```bash
$ cp nosort.go bufio.go
$ diff -u nosort.go bufio.go
--- nosort.go   2022-03-03 18:58:35.227829357 +0000
+++ bufio.go    2022-03-03 19:02:03.913590177 +0000
@@ -1,6 +1,7 @@
 package main

 import (
+       "bufio"
        "encoding/json"
        "log"
        "os"
@@ -17,7 +18,9 @@
                return stdlibEncoder(out, obj)
        }

-       _, err := out.Write([]byte("["))
+       bo := bufio.NewWriter(out)
+       defer bo.Flush()
+       _, err := bo.Write([]byte("["))
        if err != nil {
                return err
        }
@@ -25,7 +28,7 @@
        for i, row := range a {
                // Write a comma before the current object
                if i > 0 {
-                       _, err = out.Write([]byte(",\n"))
+                       _, err = bo.Write([]byte(",\n"))
                        if err != nil {
                                return err
                        }
@@ -39,15 +42,14 @@
                                return err
                        }

-                       _, err = out.Write(bs)
+                       _, err = bo.Write(bs)
                        if err != nil {
                                return err
                        }
-
                        continue
                }

-               _, err := out.Write([]byte("{"))
+               _, err := bo.Write([]byte("{"))
                if err != nil {
                        return err
                }
@@ -58,13 +60,13 @@

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
@@ -74,19 +76,19 @@
                                return err
                        }

-                       _, err = out.Write(bs)
+                       _, err = bo.Write(bs)
                        if err != nil {
                                return err
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
2022/03/03 19:11:12 profile: cpu profiling enabled, /tmp/profile1195717494/cpu.pprof
2022/03/03 19:11:19 profile: cpu profiling disabled, /tmp/profile1195717494/cpu.pprof
```

Roughly 7 seconds. Not bad down from 49 seconds! But let's see where
we're spending time now.

```bash
$ go tool pprof -top /tmp/profile1195717494/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 7:11pm (UTC)
Duration: 6.41s, Total samples = 6.26s (97.60%)
Showing nodes accounting for 5.79s, 92.49% of 6.26s total
Dropped 47 nodes (cum <= 0.03s)
      flat  flat%   sum%        cum   cum%
     1.69s 27.00% 27.00%      1.88s 30.03%  encoding/json.(*encodeState).string
     0.64s 10.22% 37.22%      0.71s 11.34%  syscall.Syscall
     0.44s  7.03% 44.25%      0.76s 12.14%  strconv.appendQuotedWith
     0.43s  6.87% 51.12%      0.43s  6.87%  runtime.memmove
     0.29s  4.63% 55.75%      0.69s 11.02%  runtime.mallocgc
     0.29s  4.63% 60.38%      0.29s  4.63%  runtime.memclrNoHeapPointers
     0.24s  3.83% 64.22%      0.31s  4.95%  strconv.appendEscapedRune
     0.16s  2.56% 66.77%      0.16s  2.56%  runtime.nextFreeFast (inline)
     0.14s  2.24% 69.01%      0.97s 15.50%  bufio.(*Writer).Write
     0.11s  1.76% 70.77%      0.15s  2.40%  runtime.mapaccess2
     0.10s  1.60% 72.36%      0.19s  3.04%  runtime.mapiternext
     0.09s  1.44% 73.80%      0.16s  2.56%  runtime.concatstrings
     0.08s  1.28% 75.08%      0.08s  1.28%  reflect.Value.String
     0.07s  1.12% 76.20%      0.07s  1.12%  strconv.IsPrint
     0.06s  0.96% 77.16%      3.38s 53.99%  encoding/json.Marshal
     0.06s  0.96% 78.12%      6.26s   100%  main.nosortEncoder
     0.06s  0.96% 79.07%      0.31s  4.95%  runtime.rawbyteslice
     0.06s  0.96% 80.03%      0.10s  1.60%  sync.(*Pool).Put
     0.06s  0.96% 80.99%      0.09s  1.44%  sync.(*Pool).pin
     0.05s   0.8% 81.79%      2.49s 39.78%  encoding/json.(*encodeState).marshal
     0.05s   0.8% 82.59%      0.06s  0.96%  runtime.(*bmap).overflow (inline)
     0.05s   0.8% 83.39%      0.55s  8.79%  runtime.growslice
     0.05s   0.8% 84.19%      0.06s  0.96%  runtime.reentersyscall
     0.05s   0.8% 84.98%      0.05s   0.8%  strconv.ryuDigits32
     0.04s  0.64% 85.62%      0.04s  0.64%  bytes.(*Buffer).tryGrowByReslice (inline)
     0.04s  0.64% 86.26%      0.04s  0.64%  runtime.acquirem (inline)
     0.04s  0.64% 86.90%      0.20s  3.19%  runtime.concatstring2
     0.04s  0.64% 87.54%      0.21s  3.35%  sync.(*Map).Load
     0.03s  0.48% 88.02%      0.12s  1.92%  encoding/json.newEncodeState
     0.03s  0.48% 88.50%      0.22s  3.51%  runtime.makeslice
     0.03s  0.48% 88.98%      0.38s  6.07%  runtime.stringtoslicebyte
     0.03s  0.48% 89.46%      0.09s  1.44%  strconv.ryuDigits
     0.02s  0.32% 89.78%      1.98s 31.63%  encoding/json.stringEncoder
     0.02s  0.32% 90.10%      0.25s  3.99%  encoding/json.valueEncoder
     0.02s  0.32% 90.42%      0.05s   0.8%  runtime.slicebytetostring
     0.02s  0.32% 90.73%      0.15s  2.40%  strconv.genericFtoa
     0.02s  0.32% 91.05%      1.05s 16.77%  strconv.quoteWith (inline)
     0.02s  0.32% 91.37%      0.08s  1.28%  sync.(*Pool).Get
     0.01s  0.16% 91.53%      0.74s 11.82%  bufio.(*Writer).Flush
     0.01s  0.16% 91.69%      0.04s  0.64%  bytes.(*Buffer).WriteByte
     0.01s  0.16% 91.85%      0.15s  2.40%  bytes.(*Buffer).WriteString
     0.01s  0.16% 92.01%      0.73s 11.66%  os.(*File).Write
     0.01s  0.16% 92.17%      0.13s  2.08%  runtime.(*mcache).refill
     0.01s  0.16% 92.33%      0.07s  1.12%  runtime.(*mheap).allocSpan
     0.01s  0.16% 92.49%      0.10s  1.60%  strconv.ryuFtoaShortest
         0     0% 92.49%      2.41s 38.50%  encoding/json.(*encodeState).reflectValue
         0     0% 92.49%      0.18s  2.88%  encoding/json.floatEncoder.encode
         0     0% 92.49%      0.21s  3.35%  encoding/json.typeEncoder
         0     0% 92.49%      0.72s 11.50%  internal/poll.(*FD).Write
         0     0% 92.49%      0.71s 11.34%  internal/poll.ignoringEINTRIO (inline)
         0     0% 92.49%      6.26s   100%  main.main
         0     0% 92.49%      0.72s 11.50%  os.(*File).write (inline)
         0     0% 92.49%      0.14s  2.24%  runtime.(*mcache).nextFree
         0     0% 92.49%      0.11s  1.76%  runtime.(*mcentral).cacheSpan
         0     0% 92.49%      0.10s  1.60%  runtime.(*mcentral).grow
         0     0% 92.49%      0.10s  1.60%  runtime.(*mheap).alloc
         0     0% 92.49%      0.07s  1.12%  runtime.(*mheap).alloc.func1
         0     0% 92.49%      0.06s  0.96%  runtime.entersyscall
         0     0% 92.49%      6.26s   100%  runtime.main
         0     0% 92.49%      0.07s  1.12%  runtime.systemstack
         0     0% 92.49%      0.15s  2.40%  strconv.AppendFloat (inline)
         0     0% 92.49%      1.05s 16.77%  strconv.QuoteToASCII (inline)
         0     0% 92.49%      0.71s 11.34%  syscall.Write (inline)
         0     0% 92.49%      0.71s 11.34%  syscall.write
```

## Infinite buffer

Surprisingly, we're still spending a big chunk of time in a write
syscall. If we look at the [source code for
bufio](https://cs.opensource.google/go/go/+/refs/tags/go1.17.7:src/bufio/bufio.go;drc=refs%2Ftags%2Fgo1.17.7;l=19),
we can see that the default size if 4096. So in a big file like this
we'll still be calling the write syscall a lot.

Now bufio.Writer has an odd interface. We can only specify an exact
size for the internal buffer. We could raise this to be the max size
of integers but then that would be a huge chunk of memory we always
allocate. That doesn't really make sense.

We could instead use a bytes.Buffer that is allowed to grow. Then we
only write to the file once it's full. A lazier approach would be to
ignore it getting full (which will just cause an error to be returned
eventually and the whole encoder to fail) and just copy from the
buffer to the file once at the end. Let's give that a shot.

```bash
$ cp bufio.go buffer.go
$ diff -u bufio.go buffer.go
--- bufio.go    2022-03-03 19:02:03.913590177 +0000
+++ buffer.go   2022-03-03 19:03:38.007564957 +0000
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
@@ -89,6 +88,14 @@
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
$ ./main --in wide --encoder nosort
2022/03/03 19:12:58 profile: cpu profiling enabled, /tmp/profile3980759756/cpu.pprof
2022/03/03 19:13:04 profile: cpu profiling disabled, /tmp/profile3980759756/cpu.pprof
$ go tool pprof -top /tmp/profile3980759756/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 7:12pm (UTC)
Duration: 5.77s, Total samples = 6.57s (113.88%)
Showing nodes accounting for 5.93s, 90.26% of 6.57s total
Dropped 78 nodes (cum <= 0.03s)
      flat  flat%   sum%        cum   cum%
     1.34s 20.40% 20.40%      1.52s 23.14%  encoding/json.(*encodeState).string
     0.70s 10.65% 31.05%      0.70s 10.65%  runtime.memmove
     0.50s  7.61% 38.66%      0.74s 11.26%  strconv.appendQuotedWith
     0.32s  4.87% 43.53%      1.11s 16.89%  runtime.scanobject
     0.29s  4.41% 47.95%      0.29s  4.41%  runtime.memclrNoHeapPointers
     0.25s  3.81% 51.75%      0.65s  9.89%  runtime.mallocgc
     0.20s  3.04% 54.79%      0.71s 10.81%  bytes.(*Buffer).Write
     0.19s  2.89% 57.69%      0.23s  3.50%  strconv.appendEscapedRune
     0.17s  2.59% 60.27%      0.38s  5.78%  runtime.greyobject
     0.16s  2.44% 62.71%      0.31s  4.72%  runtime.findObject
     0.16s  2.44% 65.14%      0.16s  2.44%  runtime.pageIndexOf (inline)
     0.14s  2.13% 67.28%      0.21s  3.20%  runtime.mapaccess2
     0.10s  1.52% 68.80%      5.27s 80.21%  main.nosortEncoder
     0.10s  1.52% 70.32%      0.16s  2.44%  runtime.concatstrings
     0.10s  1.52% 71.84%      0.10s  1.52%  runtime.nextFreeFast (inline)
     0.09s  1.37% 73.21%      0.09s  1.37%  runtime.procyield
     0.08s  1.22% 74.43%      0.09s  1.37%  runtime.spanOf (inline)
     0.08s  1.22% 75.65%      0.15s  2.28%  strconv.genericFtoa
     0.08s  1.22% 76.86%      0.11s  1.67%  sync.(*Pool).Put
     0.07s  1.07% 77.93%      0.07s  1.07%  reflect.Value.String
     0.07s  1.07% 79.00%      0.56s  8.52%  runtime.growslice
     0.07s  1.07% 80.06%      0.08s  1.22%  runtime.mapiternext
     0.06s  0.91% 80.97%      0.06s  0.91%  runtime.(*mspan).divideByElemSize (inline)
     0.06s  0.91% 81.89%      0.10s  1.52%  runtime.slicebytetostring
     0.05s  0.76% 82.65%      0.07s  1.07%  sync.(*Pool).Get
     0.04s  0.61% 83.26%      3.07s 46.73%  encoding/json.Marshal
     0.04s  0.61% 83.87%      0.05s  0.76%  runtime.heapBits.next (inline)
     0.04s  0.61% 84.47%      0.04s  0.61%  strconv.IsPrint
     0.04s  0.61% 85.08%      0.28s  4.26%  sync.(*Map).Load
     0.03s  0.46% 85.54%      0.15s  2.28%  bytes.(*Buffer).WriteString
     0.03s  0.46% 86.00%      2.17s 33.03%  encoding/json.(*encodeState).reflectValue
     0.03s  0.46% 86.45%      0.31s  4.72%  encoding/json.typeEncoder
     0.03s  0.46% 86.91%      0.05s  0.76%  runtime.stringtoslicebyte
     0.03s  0.46% 87.37%      1.12s 17.05%  strconv.quoteWith (inline)
     0.02s   0.3% 87.67%      0.10s  1.52%  encoding/json.newEncodeState
     0.02s   0.3% 87.98%      1.20s 18.26%  runtime.gcDrain
     0.02s   0.3% 88.28%      0.06s  0.91%  runtime.sweepone
     0.02s   0.3% 88.58%      0.05s  0.76%  strconv.ryuDigits
     0.02s   0.3% 88.89%      0.04s  0.61%  sync.(*Pool).pin
     0.01s  0.15% 89.04%      2.24s 34.09%  encoding/json.(*encodeState).marshal
     0.01s  0.15% 89.19%      1.60s 24.35%  encoding/json.stringEncoder
     0.01s  0.15% 89.35%      0.16s  2.44%  runtime.(*mcache).refill
     0.01s  0.15% 89.50%      0.12s  1.83%  runtime.(*mcentral).grow
     0.01s  0.15% 89.65%      0.04s  0.61%  runtime.(*sweepLocked).sweep
     0.01s  0.15% 89.80%      0.17s  2.59%  runtime.concatstring2
     0.01s  0.15% 89.95%      0.31s  4.72%  runtime.makeslice
     0.01s  0.15% 90.11%      0.05s  0.76%  runtime.nilinterhash
     0.01s  0.15% 90.26%      0.04s  0.61%  runtime.typehash
         0     0% 90.26%      0.37s  5.63%  bytes.(*Buffer).grow
         0     0% 90.26%      0.06s  0.91%  bytes.makeSlice
         0     0% 90.26%      0.21s  3.20%  encoding/json.floatEncoder.encode
         0     0% 90.26%      0.33s  5.02%  encoding/json.valueEncoder
         0     0% 90.26%      5.27s 80.21%  main.main
         0     0% 90.26%      0.16s  2.44%  runtime.(*mcache).nextFree
         0     0% 90.26%      0.15s  2.28%  runtime.(*mcentral).cacheSpan
         0     0% 90.26%      0.10s  1.52%  runtime.(*mheap).alloc
         0     0% 90.26%      0.06s  0.91%  runtime.(*mspan).objIndex
         0     0% 90.26%      0.06s  0.91%  runtime.bgsweep
         0     0% 90.26%      1.20s 18.26%  runtime.gcBgMarkWorker
         0     0% 90.26%      1.20s 18.26%  runtime.gcBgMarkWorker.func2
         0     0% 90.26%      0.04s  0.61%  runtime.heapBits.initSpan
         0     0% 90.26%      5.27s 80.21%  runtime.main
         0     0% 90.26%      0.09s  1.37%  runtime.markroot
         0     0% 90.26%      0.09s  1.37%  runtime.markroot.func1
         0     0% 90.26%      0.09s  1.37%  runtime.suspendG
         0     0% 90.26%      1.28s 19.48%  runtime.systemstack
         0     0% 90.26%      0.15s  2.28%  strconv.AppendFloat (inline)
         0     0% 90.26%      1.12s 17.05%  strconv.QuoteToASCII (inline)
         0     0% 90.26%      0.05s  0.76%  strconv.ryuFtoaShortest
```

Down another half second-ish. Nice! And hey! Syscall is no longer in
there.

## Column caching

Now we're getting to the end of useful changes we can make but I
notice `strconv.appendQuotedWith` and `strconv.appendEscapedRune`. We
may be able to shave off a little bit by caching the columns rather
than escaping all columns again each time for every row. Let's try it.

```bash
$ cp buffer.go cache-columns.go
$ diff -u buffer.go cache-columns.go
--- buffer.go   2022-03-03 19:02:13.628485570 +0000
+++ cache-columns.go    2022-03-03 19:01:54.121695243 +0000
@@ -24,6 +24,8 @@
                return err
        }

+       quotedColumns := map[string][]byte{}
+
        for i, row := range a {
                // Write a comma before the current object
                if i > 0 {
@@ -65,7 +67,12 @@
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
@@ -75,7 +82,7 @@
                                return err
                        }

-                       _, err = out.Write(bs)
+                       _, err = bo.Write(bs)
                        if err != nil {
                                return err
                        }
```

And run it.

```
$ go build -o main.go cache-columns.go
$ ./main --in wide --encoder nosort
2022/03/03 19:14:08 profile: cpu profiling enabled, /tmp/profile2651087124/cpu.pprof
2022/03/03 19:14:13 profile: cpu profiling disabled, /tmp/profile2651087124/cpu.pprof
$ go tool pprof -top  /tmp/profile2651087124/cpu.pprof
File: main
Type: cpu
Time: Mar 3, 2022 at 7:14pm (UTC)
Duration: 4.98s, Total samples = 5.79s (116.28%)
Showing nodes accounting for 5.28s, 91.19% of 5.79s total
Dropped 69 nodes (cum <= 0.03s)
      flat  flat%   sum%        cum   cum%
     1.35s 23.32% 23.32%      1.47s 25.39%  encoding/json.(*encodeState).string
     0.49s  8.46% 31.78%      0.49s  8.46%  runtime.memmove
     0.35s  6.04% 37.82%      1.09s 18.83%  runtime.scanobject
     0.23s  3.97% 41.80%      0.23s  3.97%  runtime.memclrNoHeapPointers
     0.22s  3.80% 45.60%      0.22s  3.80%  runtime.procyield
     0.18s  3.11% 48.70%      0.18s  3.11%  runtime.pageIndexOf (inline)
     0.17s  2.94% 51.64%      0.42s  7.25%  runtime.mapaccess1_faststr
     0.14s  2.42% 54.06%      0.14s  2.42%  aeshashbody
     0.14s  2.42% 56.48%      0.27s  4.66%  runtime.findObject
     0.14s  2.42% 58.89%      0.24s  4.15%  runtime.mapiternext
     0.13s  2.25% 61.14%      0.57s  9.84%  bytes.(*Buffer).Write
     0.11s  1.90% 63.04%      0.11s  1.90%  reflect.Value.String
     0.10s  1.73% 64.77%      4.34s 74.96%  main.nosortEncoder
     0.09s  1.55% 66.32%      0.09s  1.55%  memeqbody
     0.09s  1.55% 67.88%      0.34s  5.87%  runtime.greyobject
     0.09s  1.55% 69.43%      0.09s  1.55%  strconv.ryuDigits32
     0.09s  1.55% 70.98%      0.25s  4.32%  sync.(*Map).Load
     0.08s  1.38% 72.37%      0.15s  2.59%  runtime.mapaccess2
     0.07s  1.21% 73.58%      0.07s  1.21%  reflect.Value.Type
     0.07s  1.21% 74.78%      0.07s  1.21%  runtime.heapBits.bits
     0.06s  1.04% 75.82%      2.25s 38.86%  encoding/json.(*encodeState).marshal
     0.06s  1.04% 76.86%      2.15s 37.13%  encoding/json.(*encodeState).reflectValue
     0.06s  1.04% 77.89%      0.08s  1.38%  runtime.(*bmap).overflow (inline)
     0.06s  1.04% 78.93%      0.33s  5.70%  runtime.mallocgc
     0.05s  0.86% 79.79%      0.13s  2.25%  encoding/json.newEncodeState
     0.05s  0.86% 80.66%      0.05s  0.86%  runtime.(*mspan).divideByElemSize (inline)
     0.05s  0.86% 81.52%      0.05s  0.86%  runtime.nextFreeFast (inline)
     0.05s  0.86% 82.38%      0.06s  1.04%  runtime.spanOf (inline)
     0.05s  0.86% 83.25%      0.10s  1.73%  sync.(*Pool).Put
     0.04s  0.69% 83.94%      0.10s  1.73%  bytes.(*Buffer).WriteString
     0.04s  0.69% 84.63%      0.04s  0.69%  runtime.heapBits.next (inline)
     0.04s  0.69% 85.32%      0.04s  0.69%  runtime.memhash64
     0.04s  0.69% 86.01%      0.05s  0.86%  sync.runtime_procPin
     0.03s  0.52% 86.53%      0.03s  0.52%  bytes.(*Buffer).tryGrowByReslice (partial-inline)
     0.03s  0.52% 87.05%      0.03s  0.52%  runtime.(*gcBits).bitp (inline)
     0.03s  0.52% 87.56%      0.05s  0.86%  runtime.(*mheap).allocSpan
     0.03s  0.52% 88.08%      0.03s  0.52%  runtime.add (inline)
     0.03s  0.52% 88.60%      0.03s  0.52%  runtime.markBits.isMarked (inline)
     0.03s  0.52% 89.12%      0.10s  1.73%  sync.(*Pool).pin
     0.02s  0.35% 89.46%      0.18s  3.11%  encoding/json.floatEncoder.encode
     0.02s  0.35% 89.81%      0.43s  7.43%  runtime.growslice
     0.02s  0.35% 90.16%      0.08s  1.38%  sync.(*Pool).Get
     0.01s  0.17% 90.33%      3.01s 51.99%  encoding/json.Marshal
     0.01s  0.17% 90.50%      0.26s  4.49%  encoding/json.typeEncoder
     0.01s  0.17% 90.67%      0.03s  0.52%  runtime.(*spanSet).pop
     0.01s  0.17% 90.85%      0.05s  0.86%  runtime.nilinterhash
     0.01s  0.17% 91.02%      0.14s  2.42%  strconv.genericFtoa
     0.01s  0.17% 91.19%      0.11s  1.90%  strconv.ryuFtoaShortest
         0     0% 91.19%      0.25s  4.32%  bytes.(*Buffer).grow
         0     0% 91.19%      0.06s  1.04%  bytes.makeSlice
         0     0% 91.19%      1.63s 28.15%  encoding/json.stringEncoder
         0     0% 91.19%      0.28s  4.84%  encoding/json.valueEncoder
         0     0% 91.19%      4.34s 74.96%  main.main
         0     0% 91.19%      0.03s  0.52%  runtime.(*mcache).allocLarge
         0     0% 91.19%      0.11s  1.90%  runtime.(*mcache).nextFree
         0     0% 91.19%      0.09s  1.55%  runtime.(*mcache).refill
         0     0% 91.19%      0.09s  1.55%  runtime.(*mcentral).cacheSpan
         0     0% 91.19%      0.08s  1.38%  runtime.(*mcentral).grow
         0     0% 91.19%      0.07s  1.21%  runtime.(*mheap).alloc
         0     0% 91.19%      0.05s  0.86%  runtime.(*mheap).alloc.func1
         0     0% 91.19%      0.03s  0.52%  runtime.(*mheap).freeSpan
         0     0% 91.19%      0.03s  0.52%  runtime.(*mheap).freeSpan.func1
         0     0% 91.19%      0.03s  0.52%  runtime.(*mspan).markBitsForIndex (inline)
         0     0% 91.19%      0.05s  0.86%  runtime.(*mspan).objIndex (inline)
         0     0% 91.19%      0.05s  0.86%  runtime.(*sweepLocked).sweep
         0     0% 91.19%      0.08s  1.38%  runtime.bgsweep
         0     0% 91.19%      1.33s 22.97%  runtime.gcBgMarkWorker
         0     0% 91.19%      1.33s 22.97%  runtime.gcBgMarkWorker.func2
         0     0% 91.19%      1.33s 22.97%  runtime.gcDrain
         0     0% 91.19%      0.03s  0.52%  runtime.goschedImpl
         0     0% 91.19%      0.03s  0.52%  runtime.gosched_m
         0     0% 91.19%      0.04s  0.69%  runtime.heapBits.initSpan
         0     0% 91.19%      4.34s 74.96%  runtime.main
         0     0% 91.19%      0.06s  1.04%  runtime.makeslice
         0     0% 91.19%      0.24s  4.15%  runtime.markroot
         0     0% 91.19%      0.24s  4.15%  runtime.markroot.func1
         0     0% 91.19%      0.03s  0.52%  runtime.mcall
         0     0% 91.19%      0.03s  0.52%  runtime.memclrNoHeapPointersChunked
         0     0% 91.19%      0.03s  0.52%  runtime.schedule
         0     0% 91.19%      0.24s  4.15%  runtime.suspendG
         0     0% 91.19%      0.08s  1.38%  runtime.sweepone
         0     0% 91.19%      1.42s 24.53%  runtime.systemstack
         0     0% 91.19%      0.04s  0.69%  runtime.typehash
         0     0% 91.19%      0.14s  2.42%  strconv.AppendFloat (inline)
         0     0% 91.19%      0.10s  1.73%  strconv.ryuDigits
```

Not bad! This is about as far as I can figure out how to take this
without making massive new changes. So let's call it a day on this
nosort implementation.

## goccy/go-json

Now I wonder how this implementation compares to other existing
libraries that improve on the Go standard libraries JSON encoder.

Let's add [goccy/go-json](https://github.com/goccy/go-json) which
bills itself as the fastest encoder. Let's drop `pkg/profile` and
rely solely on timings taken before and after the `encode` function
is called. And let's beef up the benchmark script a bit more to be
able to run multiple iterations and multiple kinds of encoders.

```
$ cp cache-columns.go goccy.go
$ diff -u cache-columns.go goccy.go
--- cache-columns.go    2022-03-03 19:01:54.121695243 +0000
+++ goccy.go    2022-03-03 18:51:15.265545778 +0000
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
@@ -111,10 +115,16 @@
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
@@ -123,15 +133,29 @@
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
@@ -151,16 +175,30 @@
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

-       p := profile.Start()
-       defer p.Stop()
-       err = encoder(fw, o)
-       if err != nil {
-               panic(err)
+               for i := 0; i < nTimes; i++ {
+                       fw, err := os.OpenFile(in+"-"+encoderArg+".json", os.O_TRUNC|os.O_WRONLY|os.O_CREATE, os.ModePerm)
+                       if err != nil {
+                               panic(err)
+                       }
+
+                       t1 := time.Now()
+                       err = encoder(fw, o)
+                       t2 := time.Now()
+                       if err != nil {
+                               panic(err)
+                       }
+
+                       fmt.Printf("%s,%s,%s\n", in, encoderArg, t2.Sub(t1))
+                       runtime.GC()
+
+                       err = fw.Close()
+                       if err != nil{
+                               panic(err)
+                       }
+               }
        }
 }
```

One important thing to call out here is `runtime.GC()` which forces
the GC to run in-between tests rather than during them. This helps
make the GC more predictable and less likely to influence timings
during encoding. Without this you'd see a massive growth in time taken
ever 3/4 runs.

We also can't defer closing the file since we're closing it in a loop
and there's no defer-like mechanism in Go for scheduling a thing to
run at the end of the (loop) block.

Let's try it out.

```
$ go build -o main goccy.go
$ ./main --in wide --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
wide,nosort,4.956871093s
wide,nosort,5.139428155s
wide,nosort,5.093279538s
wide,nosort,5.387918932s
wide,nosort,5.134292666s
wide,goccy_json,4.955825312s
wide,goccy_json,5.029368983s
wide,goccy_json,3.728623564s
wide,goccy_json,5.130309986s
wide,goccy_json,5.073473831s
wide,stdlib,6.788736114s
wide,stdlib,6.766644459s
wide,stdlib,6.194967849s
wide,stdlib,6.234464379s
wide,stdlib,6.809717451s
```

Woah! This was a genuine surprise. Most other benchmarks I did showed
goccy/go-json as being much faster than this nosort implementation.
So let's try some other datasets.

```bash
$ ./main --in long --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
long,nosort,5.800225163s
long,nosort,5.989665541s
long,nosort,6.004557873s
long,nosort,6.072411619s
long,nosort,5.899225226s
long,goccy_json,5.755024859s
long,goccy_json,5.434443782s
long,goccy_json,5.499432986s
long,goccy_json,5.411100532s
long,goccy_json,5.351709453s
long,stdlib,8.102073085s
long,stdlib,8.297254786s
long,stdlib,8.107278916s
long,stdlib,8.131379033s
long,stdlib,8.154066185s
```

So what we can see already is that this nosort implementation seems to
perform pretty well with large datasets, shaving at most 10-15% time
off of the standard library implementation. But it isn't necessarily
the fastest library out there.

Let's try it out against a medium-sized dataset:

```
$ fakegen --rows 100000 --cols 10 > med.json
$./main --in med --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
med,nosort,786.904739ms
med,nosort,801.232731ms
med,nosort,743.066301ms
med,nosort,700.651086ms
med,nosort,736.939572ms
med,goccy_json,527.869523ms
med,goccy_json,500.694309ms
med,goccy_json,529.841332ms
med,goccy_json,521.776871ms
med,goccy_json,520.731622ms
med,stdlib,862.493399ms
med,stdlib,840.786104ms
med,stdlib,714.077849ms
med,stdlib,862.17802ms
med,stdlib,854.657331ms
```

And a small dataset:

```
$ fakegen --rows 10000 --cols 10> small.json
./main --in small --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
small,nosort,40.682862ms
small,nosort,38.091065ms
small,nosort,37.631626ms
small,nosort,37.592715ms
small,nosort,37.357291ms
small,goccy_json,34.784181ms
small,goccy_json,23.023397ms
small,goccy_json,67.313957ms
small,goccy_json,24.348643ms
small,goccy_json,66.196051ms
small,stdlib,47.655781ms
small,stdlib,43.749318ms
small,stdlib,46.656674ms
small,stdlib,46.858409ms
small,stdlib,47.482409ms
```

And finally let's use the dataset that [octosql
uses](https://github.com/cube2222/octosql/blob/main/benchmarks/benchmarks.sh). It
is a csv but we can use [dsq](https://github.com/multiprocessio/dsq)
to convert it to JSON.

```
$ curl https://s3.amazonaws.com/nyc-tlc/trip+data/yellow_tripdata_2021-04.csv -o taxi.csv
$ dsq taxi.csv > taxi.json
$ ls -lah taxi.json
-rw-r--r-- 1 phil phil 877M Mar  3 16:40 taxi.json
$ wc taxi.json
  2171186   6513561 919169646 taxi.json
$ ./main --in taxi --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
taxi,nosort,7.318133704s
taxi,nosort,6.865036526s
taxi,nosort,6.924191823s
taxi,nosort,6.972792412s
taxi,nosort,6.912377632s
taxi,goccy_json,7.504571929s
taxi,goccy_json,7.481574296s
taxi,goccy_json,7.520564746s
taxi,goccy_json,7.543578814s
taxi,goccy_json,7.561023391s
taxi,stdlib,12.401270896s
taxi,stdlib,12.328176325s
taxi,stdlib,12.383455251s
taxi,stdlib,12.316689475s
taxi,stdlib,12.374483769s
```

Not bad!

## Composability

Now the cool thing about this nosort implementation is that we can
swap out the underlying JSON encoder library. For example, instead of
using the standard library's encoder under the hood we could use goccy:

```bash
$ cp goccy.go goccy_nosort.go
$ diff -u goccy.go goccy_nosort.go
--- goccy.go    2022-03-03 18:51:15.265545778 +0000
+++ goccy_nosort.go     2022-03-03 19:25:44.119269651 +0000
@@ -14,7 +14,7 @@
        goccy_json "github.com/goccy/go-json"
 )

-func nosortEncoder(out *os.File, obj interface{}) error {
+func nosortEncoder(out *os.File, obj interface{}, marshalFn func(o interface{}) ([]byte, error)) error {
        a, ok := obj.([]interface{})
        // Fall back to normal encoder
        if !ok {
@@ -42,7 +42,7 @@
                r, ok := row.(map[string]interface{})
                if !ok {
                        log.Println("Falling back to stdlib")
-                       bs, err := json.Marshal(row)
+                       bs, err := marshalFn(row)
                        if err != nil {
                                return err
                        }
@@ -81,7 +81,7 @@
                                return err
                        }

-                       bs, err := json.Marshal(val)
+                       bs, err := marshalFn(val)
                        if err != nil {
                                return err
                        }
@@ -152,7 +152,13 @@
                                case "stdlib":
                                        encoders = append(encoders, stdlibEncoder)
                                case "nosort":
-                                       encoders = append(encoders, nosortEncoder)
+                                       encoders = append(encoders, func(out *os.File, o interface{}) error {
+                                               return nosortEncoder(out, o, json.Marshal)
+                                       })
+                               case "nosort_goccy":
+                                       encoders = append(encoders, func(out *os.File, o interface{}) error {
+                                               return nosortEncoder(out, o, goccy_json.Marshal)
+                                       })
                                case "goccy_json":
                                        encoders = append(encoders, goccy_jsonEncoder)
                                }
```

Let's try it out against the small dataset:

```
$ ./main --in small --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
small,nosort,41.760112ms
small,nosort,37.335286ms
small,nosort,39.368679ms
small,nosort,38.287757ms
small,nosort,38.271166ms
small,nosort_goccy,27.599888ms
small,nosort_goccy,28.923579ms
small,nosort_goccy,28.135659ms
small,nosort_goccy,28.628808ms
small,nosort_goccy,28.463473ms
small,goccy_json,31.275921ms
small,goccy_json,67.421084ms
small,goccy_json,33.94129ms
small,goccy_json,31.408809ms
small,goccy_json,31.221386ms
small,stdlib,47.177755ms
small,stdlib,46.994301ms
small,stdlib,43.017482ms
small,stdlib,47.505036ms
small,stdlib,46.647982ms
```

The mid-sized dataset:

```
$ ./main --in med --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
med,nosort,782.66375ms
med,nosort,737.980525ms
med,nosort,721.492919ms
med,nosort,724.356263ms
med,nosort,736.395523ms
med,nosort_goccy,498.971623ms
med,nosort_goccy,502.579077ms
med,nosort_goccy,489.708421ms
med,nosort_goccy,526.048878ms
med,nosort_goccy,512.748401ms
med,goccy_json,532.466736ms
med,goccy_json,534.507837ms
med,goccy_json,543.230595ms
med,goccy_json,533.324592ms
med,goccy_json,530.899822ms
med,stdlib,863.344366ms
med,stdlib,697.312404ms
med,stdlib,868.055438ms
med,stdlib,868.654749ms
med,stdlib,897.503696ms
```

The long dataset:

```
$ ./main --in long --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
long,nosort,5.916875793s
long,nosort,6.039521791s
long,nosort,5.935543183s
long,nosort,6.036550077s
long,nosort,6.011574246s
long,nosort_goccy,4.813237568s
long,nosort_goccy,4.761463935s
long,nosort_goccy,4.752175775s
long,nosort_goccy,4.798997185s
long,nosort_goccy,4.695403759s
long,goccy_json,5.800176224s
long,goccy_json,5.409573733s
long,goccy_json,5.36512912s
long,goccy_json,5.418035519s
long,goccy_json,5.411432234s
long,stdlib,8.105650617s
long,stdlib,8.024426906s
long,stdlib,8.038723257s
long,stdlib,8.089056904s
long,stdlib,8.046626953s
```

The wide dataset:

```
$ ./main --in wide --encoders nosort,goccy_json,stdlib --ntimes 5
sample,encoder,time
wide,nosort,4.966890211s
wide,nosort,5.10385764s
wide,nosort,5.209565609s
wide,nosort,5.05580971s
wide,nosort,5.128548152s
wide,nosort_goccy,3.807389446s
wide,nosort_goccy,3.946759042s
wide,nosort_goccy,3.786206428s
wide,nosort_goccy,3.857447258s
wide,nosort_goccy,3.719183236s
wide,goccy_json,4.982229773s
wide,goccy_json,5.056007992s
wide,goccy_json,4.98831937s
wide,goccy_json,4.9149848s
wide,goccy_json,4.89111462s
wide,stdlib,6.818520461s
wide,stdlib,6.79955319s
wide,stdlib,6.785183651s
wide,stdlib,6.713526793s
wide,stdlib,6.741904743s
```

And the taxi dataset:

```
./main --in taxi --encoders nosort,nosort_goccy,goccy_json,stdlib --ntimes 5
sample,encoder,time
taxi,nosort,7.441821343s
taxi,nosort,7.16027916s
taxi,nosort,7.114210802s
taxi,nosort,6.970729169s
taxi,nosort,6.976680741s
taxi,nosort_goccy,5.306546435s
taxi,nosort_goccy,5.314004524s
taxi,nosort_goccy,5.21857126s
taxi,nosort_goccy,5.254188054s
taxi,nosort_goccy,5.161521902s
taxi,goccy_json,7.484639889s
taxi,goccy_json,6.2012459s
taxi,goccy_json,7.671579687s
taxi,goccy_json,7.594733731s
taxi,goccy_json,7.514168117s
taxi,stdlib,12.551869909s
taxi,stdlib,12.294643142s
taxi,stdlib,11.52487468s
taxi,stdlib,11.410906914s
taxi,stdlib,12.228855201s
```

That's about a 55% speed improvement on the standard library
encoder. That's pretty good!

## Validate

Finally, let's pass through the nosort generated JSON and have it be
encoded with the standard libary JSON encoder. Then if there is no
diff between that result and the stdlib encoded JSON, we'll know that
we have emitted correct and valid JSON.

```
$ ./main --in taxi-nosort
sample,encoder,time
taxi-nosort,stdlib,13.00740141s
$ diff taxi-nosort-stdlib.json taxi-stdlib.json
$ echo $?
0
```

Okee doke. :)

## Fin

What's neat is how much we can improve on the standard library without
reimplementing the hairiest parts of JSON encoding like actual value
reflection.

If you want to run these benchmarks for yourself, the [code is all on
Github](https://github.com/multiprocessio/go-json-benchmarks).

I'm also working on breaking this out as a standalone library. You can
[check it out on Github](https://github.com/multiprocessio/go-json).

## Caveat

The results here are surprisingly good. Surprisingly good in these
situations normally means you messed up. So, Internet, do your thing
and correct me where I'm wrong!

## Machine specs
I am running these benchmarks on a dedicated bare metal instance, [OVH
Rise-1](https://us.ovhcloud.com/bare-metal/rise/rise-1/).

* RAM: 64 GB DDR4 ECC 2,133 MHz
* Disk: 2x450 GB SSD NVMe in Soft RAID
* Processor: Intel Xeon E3-1230v6 - 4c/8t - 3.5 GHz/3.9 GHz

#### Share
<blockquote class="twitter-tweet"><p lang="en" dir="ltr">New blog post! On the slight modification we make to DataStation&#39;s JSON encoder to improve performance when writing large arrays of objects.<a href="https://t.co/wkwP7aW6HB">https://t.co/wkwP7aW6HB</a> <a href="https://t.co/y0wNDV3Bma">pic.twitter.com/y0wNDV3Bma</a></p>&mdash; Multiprocess Labs (@multiprocessio) <a href="https://twitter.com/multiprocessio/status/1499492400703619077?ref_src=twsrc%5Etfw">March 3, 2022</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>

{% endblock %}
